import pytest
from utils.constants import ROLES, MAX_INT, WEEK


@pytest.fixture(scope="session")
def amount():
    return 1_000_000 * 10**18


@pytest.fixture(scope="session")
def gov(accounts):
    return accounts[0]


@pytest.fixture(scope="session")
def fee_manager(accounts):
    return accounts[1]


@pytest.fixture(scope="session")
def random_user(accounts):
    return accounts[3]


@pytest.fixture(scope="session")
def create_token(project, gov, amount):
    def create_token(name, decimals=18):
        token = gov.deploy(project.Token, name, decimals)
        token.mint(gov.address, amount, sender=gov)
        return token

    yield create_token


@pytest.fixture(scope="session")
def asset(create_token):
    return create_token("asset")


@pytest.fixture
def create_simple_accountant(project, fee_manager):
    def create_simple_accountant(max_management_fee: int = 500, max_performance_fee: int = 500):
        return fee_manager.deploy(project.SimpleAccountant, max_management_fee, max_performance_fee)

    yield create_simple_accountant


@pytest.fixture(scope="function")
def simple_accountant(create_simple_accountant):
    yield create_simple_accountant()


@pytest.fixture(scope="function")
def create_strategy(project, gov, asset):
    def create_strategy(vault):
        return gov.deploy(project.MockStrategy, asset.address, vault.address)

    yield create_strategy


@pytest.fixture(scope="function")
def create_vault(project, gov):
    def create_vault(accountant, asset):
        vault = gov.deploy(
            project.dependencies["yearn-vaults"]["master"].VaultV3,
            asset,
            "VaultV3_Mock",
            "VV3_Mock",
            gov,
            WEEK
        )
        vault.set_role(
            gov.address,
            ROLES.STRATEGY_MANAGER | ROLES.DEBT_MANAGER | ROLES.ACCOUNTING_MANAGER,
            sender=gov,
        )
        # set up fee manager
        vault.set_accountant(accountant.address, sender=gov)

        # set vault deposit
        vault.set_deposit_limit(MAX_INT, sender=gov)
        return vault

    yield create_vault


@pytest.fixture(scope="function")
def vault(asset, create_vault):
    vault = create_vault(asset)
    yield vault


@pytest.fixture(scope="session")
def user_deposit(asset):
    def user_deposit(user, vault, amount):
        initial_balance = asset.balanceOf(vault)
        if asset.allowance(user, vault) < amount:
            asset.approve(vault.address, MAX_INT, sender=user)
        vault.deposit(amount, user.address, sender=user)
        assert asset.balanceOf(vault) == initial_balance + amount

    return user_deposit


@pytest.fixture(scope="session")
def add_debt_to_strategy(gov):
    def add_debt_to_strategy(strategy, vault, target_debt):
        vault.update_max_debt_for_strategy(strategy.address, target_debt, sender=gov)
        vault.update_debt(strategy.address, target_debt, sender=gov)

    return add_debt_to_strategy
