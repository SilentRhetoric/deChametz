from algopy import (
    ARC4Contract,
    Asset,
    Bytes,
    Global,
    LocalState,
    Txn,
    UInt64,
    arc4,
    itxn,
)


class Sale(arc4.Struct):
    seller: arc4.Address
    time: arc4.UInt64
    chametz_sold: arc4.String


class Repurchase(arc4.Struct):
    buyer: arc4.Address
    time: arc4.UInt64
    chametz_repurchased: arc4.String


class Dechametz(ARC4Contract):
    def __init__(self) -> None:
        self.is_jewish = Bytes(b"no")
        self.token_asset_id = UInt64(0)
        self.chametz_sold = LocalState(
            Bytes,
            key="chametz_sold",
            description="Description of the chametz sold",
        )

    @arc4.abimethod()
    def bootstrap(self) -> UInt64:
        assert Txn.sender == Global.creator_address
        assert self.token_asset_id == 0
        self.token_asset_id = (
            itxn.AssetConfig(
                total=10000000000,
                decimals=0,
                default_frozen=True,
                asset_name="ForChametz",
                unit_name="4CHAMETZ",
                url="https://dechametz.me",
                manager=Global.current_application_address,
                reserve=Global.current_application_address,
                freeze=Global.current_application_address,
                clawback=Global.current_application_address,
                fee=0,
            )
            .submit()
            .created_asset.id
        )
        return self.token_asset_id

    @arc4.abimethod(create="disallow", allow_actions=["OptIn"], name="Sell chametz")
    def sell_chametz(self, chametz: Bytes) -> None:
        assert Txn.sender.is_opted_in(
            Asset(self.token_asset_id)
        ), "Sender must have opted in to the ForChametz token"
        assert (
            Asset(self.token_asset_id).balance(Txn.sender) == 0
        ), "Must not be holding a ForChametz token already to sell chametz"
        assert Txn.sender.is_opted_in(
            Global.current_application_id
        ), "Sender must opt-in to the smart contract"
        self.chametz_sold[Txn.sender] = chametz
        itxn.AssetTransfer(
            xfer_asset=self.token_asset_id,
            asset_amount=1,
            sender=Global.current_application_address,
            # asset_sender=Global.current_application_address,  # Currently unsupported in Puya
            asset_receiver=Txn.sender,
            note=b"Sell" + chametz,
            fee=0,
        ).submit()
        arc4.emit(
            Sale(
                seller=arc4.Address(Txn.sender),
                time=arc4.UInt64(Global.latest_timestamp),
                chametz_sold=arc4.String.from_bytes(chametz),
            )
        )

    @arc4.abimethod(
        create="disallow", allow_actions=["CloseOut"], name="Repurchase chametz"
    )
    def repurchase_chametz(self) -> None:
        assert (
            Asset(self.token_asset_id).balance(Txn.sender) == 1
        ), "Must hold a ForChametz token to repurchase chametz"
        itxn.AssetTransfer(
            xfer_asset=self.token_asset_id,
            sender=Global.current_application_address,
            # asset_sender=Txn.sender,  # Currently unsupported in Puya
            asset_receiver=Global.current_application_address,
            note=b"Repurchase" + self.chametz_sold[Txn.sender],
            fee=0,
        ).submit()
        arc4.emit(
            Repurchase(
                buyer=arc4.Address(Txn.sender),
                time=arc4.UInt64(Global.latest_timestamp),
                chametz_repurchased=arc4.String.from_bytes(
                    self.chametz_sold[Txn.sender]
                ),
            )
        )
