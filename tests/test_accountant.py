import pytest
import ape
from utils.constants import ZERO_ADDRESS, YEAR, ROLES, REL_ERROR, MAX_BPS


def test_deployment(simple_accountant, fee_manager):
    assert simple_accountant.fee_manager() == fee_manager.address


def test_set_performance_fee__invalid_user(random_user, simple_accountant):
    random_strategy = "0x0000000000000000000000000000000000000001"
    performance_fee = 5_000

    with ape.reverts("not fee manager"):
        simple_accountant.set_performance_fee(
            random_strategy, performance_fee, sender=random_user
        )


def test_set_management_fee__invalid_user(random_user, simple_accountant):
    random_strategy = "0x0000000000000000000000000000000000000001"
    management_fee = 5_000

    with ape.reverts("not fee manager"):
        simple_accountant.set_management_fee(
            random_strategy, management_fee, sender=random_user
        )


@pytest.mark.parametrize("performance_fee", [0, 250, 500])
def test_set_performance_fee__with_valid_performance_fee(
    fee_manager, simple_accountant, performance_fee
):
    random_strategy = "0x0000000000000000000000000000000000000001"

    tx = simple_accountant.set_performance_fee(
        random_strategy, performance_fee, sender=fee_manager
    )
    event = list(tx.decode_logs(simple_accountant.UpdatePerformanceFee))

    assert len(event) == 1
    assert event[0].performance_fee == performance_fee

    assert simple_accountant.fees(random_strategy).performance_fee == performance_fee


@pytest.mark.parametrize("performance_fee", [501, 5_000, 10_000])
def test_set_performance_fee__with_in_valid_performance_fee__reverts(
    fee_manager, simple_accountant, performance_fee
):
    random_strategy = "0x0000000000000000000000000000000000000001"

    with ape.reverts("exceeds performance fee threshold"):
        simple_accountant.set_performance_fee(
            random_strategy, performance_fee, sender=fee_manager
        )


@pytest.mark.parametrize("management_fee", [0, 250, 500])
def test_set_management_fee__with_valid_management_fee(
    fee_manager, simple_accountant, management_fee
):
    random_strategy = "0x0000000000000000000000000000000000000001"

    tx = simple_accountant.set_management_fee(
        random_strategy, management_fee, sender=fee_manager
    )
    event = list(tx.decode_logs(simple_accountant.UpdateManagementFee))

    assert len(event) == 1
    assert event[0].management_fee == management_fee

    assert simple_accountant.fees(random_strategy).management_fee == management_fee


@pytest.mark.parametrize("management_fee", [501, 5_000, 10_000])
def test_set_management_fee__with_in_valid_management_fee__reverts(
    fee_manager, simple_accountant, management_fee
):
    random_strategy = "0x0000000000000000000000000000000000000001"

    with ape.reverts("exceeds management fee threshold"):
        simple_accountant.set_management_fee(
            random_strategy, management_fee, sender=fee_manager
        )


def test_propose_fee_manager__with_new_fee_manager(
    fee_manager, random_user, simple_accountant
):
    with ape.reverts("not fee manager"):
        simple_accountant.propose_fee_manager(random_user.address, sender=random_user)

    with ape.reverts("future fee manager != zero address"):
        simple_accountant.propose_fee_manager(ZERO_ADDRESS, sender=fee_manager)

    tx = simple_accountant.propose_fee_manager(random_user.address, sender=fee_manager)
    event = list(tx.decode_logs(simple_accountant.ProposeFeeManager))

    assert len(event) == 1
    assert event[0].fee_manager == random_user.address

    assert simple_accountant.future_fee_manager() == random_user.address


def test_accept_fee_manager__with_new_fee_manager(
    fee_manager, random_user, simple_accountant
):
    simple_accountant.propose_fee_manager(random_user.address, sender=fee_manager)

    with ape.reverts("not future fee manager"):
        simple_accountant.accept_fee_manager(sender=fee_manager)

    tx = simple_accountant.accept_fee_manager(sender=random_user)
    event = list(tx.decode_logs(simple_accountant.AcceptFeeManager))

    assert len(event) == 1
    assert event[0].fee_manager == random_user.address

    assert simple_accountant.fee_manager() == random_user.address
    assert simple_accountant.future_fee_manager() == random_user.address


def test_distribute__not_fee_manager__reverts(
    fee_manager, random_user, simple_accountant
):
    random_vault = "0x0000000000000000000000000000000000000001"
    assert simple_accountant.fee_manager() == fee_manager.address
    with ape.reverts("not fee manager"):
        simple_accountant.distribute(random_vault, sender=random_user)


def test_performance_fee_threshold(random_user, simple_accountant):
    assert simple_accountant.performance_fee_threshold() == 500


def test_management_fee_threshold(random_user, simple_accountant):
    assert simple_accountant.management_fee_threshold() == 500


def test_report__no_gain_no_loss(
    simple_accountant, asset, create_vault, create_strategy, gov
):
    vault = create_vault(simple_accountant, asset)
    strategy = create_strategy(vault)
    vault.add_strategy(strategy.address, sender=gov)

    total_fees, total_refunds = simple_accountant.report(
        strategy.address, 0, 0, sender=vault
    )

    assert total_fees == 0
    assert total_refunds == 0


def test_report__no_fees(
    fee_manager, simple_accountant, asset, create_vault, create_strategy, gov
):
    vault = create_vault(simple_accountant, asset)
    strategy = create_strategy(vault)
    vault.add_strategy(strategy.address, sender=gov)

    total_fees, total_refunds = simple_accountant.report(
        strategy.address, 100, 0, sender=vault
    )
    assert total_fees == 0
    assert total_refunds == 0

    total_fees, total_refunds = simple_accountant.report(
        strategy.address, 100, 0, sender=vault
    )
    assert total_fees == 0
    assert total_refunds == 0


@pytest.mark.parametrize("gain", [10**23, 10**27, 10**30])
@pytest.mark.parametrize("management_fee", [100, 500])
def test_report__gains_management_fee(
    gain,
    management_fee,
    chain,
    amount,
    asset,
    fee_manager,
    simple_accountant,
    create_vault,
    create_strategy,
    add_debt_to_strategy,
    user_deposit,
    gov,
):
    vault = create_vault(simple_accountant, asset)
    strategy = create_strategy(vault)
    vault.add_strategy(strategy.address, sender=gov)

    user_deposit(gov, vault, amount)
    add_debt_to_strategy(strategy, vault, amount)

    simple_accountant.set_management_fee(strategy, management_fee, sender=fee_manager)

    chain.pending_timestamp = chain.pending_timestamp + YEAR
    chain.mine(timestamp=chain.pending_timestamp)

    total_fees, total_refunds = simple_accountant.report(
        strategy.address, gain, 0, sender=vault
    )

    assert pytest.approx(total_fees, REL_ERROR) == amount * management_fee / MAX_BPS
    assert total_refunds == 0


@pytest.mark.parametrize("gain", [10**23, 10**27, 10**30])
@pytest.mark.parametrize("performance_fee", [100, 500])
def test_report__gains_performance_fee(
    gain,
    performance_fee,
    amount,
    asset,
    fee_manager,
    simple_accountant,
    create_vault,
    create_strategy,
    add_debt_to_strategy,
    user_deposit,
    gov,
):
    vault = create_vault(simple_accountant, asset)
    strategy = create_strategy(vault)
    vault.add_strategy(strategy.address, sender=gov)

    user_deposit(gov, vault, amount)
    add_debt_to_strategy(strategy, vault, amount)

    simple_accountant.set_performance_fee(strategy, performance_fee, sender=fee_manager)

    total_fees, total_refunds = simple_accountant.report(
        strategy.address, gain, 0, sender=vault
    )

    assert pytest.approx(total_fees, REL_ERROR) == gain * performance_fee / MAX_BPS


@pytest.mark.parametrize("gain", [10**23, 10**27, 10**30])
@pytest.mark.parametrize("performance_fee", [100, 500])
@pytest.mark.parametrize("management_fee", [100, 500])
def test_report__gains_all_fees(
    gain,
    performance_fee,
    management_fee,
    chain,
    amount,
    asset,
    fee_manager,
    simple_accountant,
    create_vault,
    create_strategy,
    add_debt_to_strategy,
    user_deposit,
    gov,
):
    vault = create_vault(simple_accountant, asset)
    strategy = create_strategy(vault)
    vault.add_strategy(strategy.address, sender=gov)

    user_deposit(gov, vault, amount)
    add_debt_to_strategy(strategy, vault, amount)

    chain.pending_timestamp = chain.pending_timestamp + YEAR
    chain.mine(timestamp=chain.pending_timestamp)

    simple_accountant.set_performance_fee(strategy, performance_fee, sender=fee_manager)
    simple_accountant.set_management_fee(strategy, management_fee, sender=fee_manager)

    total_fees, total_refunds = simple_accountant.report(
        strategy.address, gain, 0, sender=vault
    )

    assert (
        pytest.approx(total_fees, REL_ERROR)
        == gain * performance_fee / MAX_BPS + amount * management_fee / MAX_BPS
    )


@pytest.mark.parametrize("loss", [10**23, 10**27, 10**30])
@pytest.mark.parametrize("performance_fee", [100, 500])
def test_report__loss_performance_fee(
    loss,
    performance_fee,
    amount,
    asset,
    fee_manager,
    simple_accountant,
    create_vault,
    create_strategy,
    add_debt_to_strategy,
    user_deposit,
    gov,
):
    vault = create_vault(simple_accountant, asset)
    strategy = create_strategy(vault)
    vault.add_strategy(strategy.address, sender=gov)

    user_deposit(gov, vault, amount)
    add_debt_to_strategy(strategy, vault, amount)

    simple_accountant.set_performance_fee(strategy, performance_fee, sender=fee_manager)

    total_fees, total_refunds = simple_accountant.report(
        strategy.address, 0, loss, sender=vault
    )

    assert pytest.approx(total_fees, REL_ERROR) == 0
    assert total_refunds == 0


@pytest.mark.parametrize("loss", [10**23, 10**27, 10**30])
@pytest.mark.parametrize("management_fee", [100, 500])
def test_report__loss_management_fee(
    loss,
    management_fee,
    chain,
    amount,
    asset,
    fee_manager,
    simple_accountant,
    create_vault,
    create_strategy,
    add_debt_to_strategy,
    user_deposit,
    gov,
):
    vault = create_vault(simple_accountant, asset)
    strategy = create_strategy(vault)
    vault.add_strategy(strategy.address, sender=gov)

    user_deposit(gov, vault, amount)
    add_debt_to_strategy(strategy, vault, amount)

    chain.pending_timestamp = chain.pending_timestamp + YEAR
    chain.mine(timestamp=chain.pending_timestamp)

    simple_accountant.set_management_fee(strategy, management_fee, sender=fee_manager)

    total_fees, total_refunds = simple_accountant.report(
        strategy.address, 0, loss, sender=vault
    )

    assert pytest.approx(total_fees, REL_ERROR) == 0
    assert total_refunds == 0


def test_distribute__invalid_user__reverts(
    simple_accountant, asset, create_vault, random_user
):
    vault = create_vault(simple_accountant, asset)
    with ape.reverts("not fee manager"):
        simple_accountant.distribute(vault, sender=random_user)


def test_distribute(
    fee_manager, random_user, simple_accountant, create_vault, gov, asset
):
    vault = create_vault(simple_accountant, asset)

    assert asset.balanceOf(simple_accountant) == 0
    assert vault.balanceOf(simple_accountant) == 0

    asset.mint(simple_accountant.address, 100, sender=gov)
    asset.approve(vault.address, 1000000, sender=simple_accountant)
    vault.deposit(100, simple_accountant.address, sender=simple_accountant)
    assert vault.balanceOf(simple_accountant) == 100

    assert vault.balanceOf(fee_manager) == 0

    simple_accountant.distribute(vault, sender=fee_manager)

    assert vault.balanceOf(simple_accountant) == 0
    assert vault.balanceOf(fee_manager) == 100


@pytest.mark.parametrize("gain", [10**15, 10**18, 10**22])
@pytest.mark.parametrize("performance_fee", [100, 500])
@pytest.mark.parametrize("management_fee", [100, 500])
def test_report__gains_cap_to_75_percent_gain(
    gain,
    performance_fee,
    management_fee,
    chain,
    amount,
    asset,
    fee_manager,
    simple_accountant,
    create_vault,
    create_strategy,
    add_debt_to_strategy,
    user_deposit,
    gov,
):
    vault = create_vault(simple_accountant, asset)
    strategy = create_strategy(vault)
    vault.add_strategy(strategy.address, sender=gov)

    user_deposit(gov, vault, amount)
    add_debt_to_strategy(strategy, vault, amount)

    chain.pending_timestamp = chain.pending_timestamp + YEAR
    chain.mine(timestamp=chain.pending_timestamp)

    simple_accountant.set_performance_fee(strategy, performance_fee, sender=fee_manager)
    simple_accountant.set_management_fee(strategy, management_fee, sender=fee_manager)

    total_fees, total_refunds = simple_accountant.report(
        strategy.address, gain, 0, sender=vault
    )

    assert (
        pytest.approx(total_fees, REL_ERROR)
        == 7_500 * gain / MAX_BPS
    )