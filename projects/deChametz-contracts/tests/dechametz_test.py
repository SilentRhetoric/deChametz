import algokit_utils
import pytest
from algokit_utils import (
    ABITransactionResponse,
    OperationPerformed,
    TransactionParameters,
    TransferParameters,
    get_localnet_default_account,
    transfer,
)
from algokit_utils.config import config
from algosdk import constants
from algosdk.atomic_transaction_composer import ABIResult, TransactionWithSigner
from algosdk.transaction import AssetOptInTxn
from algosdk.v2client.algod import AlgodClient
from algosdk.v2client.indexer import IndexerClient

from smart_contracts.artifacts.dechametz.client import Composer, DechametzClient


@pytest.fixture(scope="session")
def dechametz_client(
    algod_client: AlgodClient, indexer_client: IndexerClient
) -> DechametzClient:
    config.configure(
        debug=True,
        # trace_all=True,
    )

    app_creator = get_localnet_default_account(algod_client)

    client = DechametzClient(
        algod_client,
        creator=app_creator,
        indexer_client=indexer_client,
        sender=app_creator.address,
        signer=app_creator.signer,
    )

    deploy_response = client.deploy(
        on_schema_break=algokit_utils.OnSchemaBreak.AppendApp,
        on_update=algokit_utils.OnUpdate.AppendApp,
    )

    # If only just created, creator funds smart contract account
    if deploy_response.action_taken in [
        OperationPerformed.Create,
        OperationPerformed.Replace,
    ]:
        transfer_parameters = TransferParameters(
            from_account=app_creator,
            to_address=client.app_address,
            micro_algos=200_000,
        )
        transfer(client.algod_client, transfer_parameters)

    return client


def test_check_religion(dechametz_client: DechametzClient) -> None:
    assert dechametz_client.get_global_state().is_jewish.as_bytes == b"no"


def test_bootstrap(dechametz_client: DechametzClient) -> None:
    asset_id = dechametz_client.get_global_state().token_asset_id
    if asset_id == 0:
        sp = dechametz_client.algod_client.suggested_params()
        sp.flat_fee = True
        sp.fee = constants.min_txn_fee * 2
        result = dechametz_client.bootstrap(
            transaction_parameters=TransactionParameters(suggested_params=sp)
        )
        asset_id = dechametz_client.get_global_state().token_asset_id
        assert result.return_value > 0
        assert asset_id == result.return_value
    else:
        assert asset_id > 0


@pytest.fixture(scope="session")
def sell_chametz(dechametz_client: DechametzClient) -> list[ABIResult]:
    asset_id = dechametz_client.get_global_state().token_asset_id
    sp = dechametz_client.algod_client.suggested_params()
    atc = dechametz_client.compose().atc
    atc.add_transaction(
        TransactionWithSigner(
            txn=AssetOptInTxn(sender=dechametz_client.sender, index=asset_id, sp=sp),  # type: ignore
            signer=dechametz_client.signer,  # type: ignore
        )
    )
    composer = Composer(app_client=dechametz_client.app_client, atc=atc)  # type: ignore

    # For the next txn, double the fee to cover the app's innerTxn
    sp.flat_fee = True
    sp.fee = constants.min_txn_fee * 2
    composer.opt_in_sell_chametz(
        chametz=b"All my bread and cookies",
        transaction_parameters=TransactionParameters(
            suggested_params=sp, foreign_assets=[asset_id]
        ),
    )
    result = composer.execute().abi_results
    return result


def test_sell_chametz_confirmed(
    dechametz_client: DechametzClient, sell_chametz: list[ABIResult]
) -> None:
    assert sell_chametz[1].tx_id is not None


def test_sell_chametz_asset_balance(
    dechametz_client: DechametzClient, sell_chametz: list[ABIResult]
) -> None:
    asset_id = dechametz_client.get_global_state().token_asset_id
    asset_info = dechametz_client.algod_client.account_asset_info(
        address=dechametz_client.sender, asset_id=asset_id  # type: ignore
    )

    assert isinstance(asset_info, dict)
    assert asset_info["asset-holding"]["amount"] == 1  # type: ignore


@pytest.fixture(scope="session")
def repurchase_chametz(
    dechametz_client: DechametzClient,
) -> ABITransactionResponse[None]:
    sp = dechametz_client.algod_client.suggested_params()
    # Double up the fee to cover the app's innerTxn
    sp.flat_fee = True
    sp.fee = constants.min_txn_fee * 2

    result = dechametz_client.close_out_repurchase_chametz(
        transaction_parameters=TransactionParameters(suggested_params=sp)
    )
    return result


def test_repurchase_chametz_confirmed(
    dechametz_client: DechametzClient, repurchase_chametz: ABITransactionResponse[None]
) -> None:
    assert repurchase_chametz.confirmed_round is not None


def test_repurchase_chametz_asset_balance(
    dechametz_client: DechametzClient, repurchase_chametz: ABITransactionResponse[None]
) -> None:
    asset_id = dechametz_client.get_global_state().token_asset_id
    asset_info = dechametz_client.algod_client.account_asset_info(
        address=dechametz_client.sender, asset_id=asset_id  # type: ignore
    )
    assert isinstance(asset_info, dict)
    assert asset_info["asset-holding"]["amount"] == 0  # type: ignore
