import json
import random
from web3 import Web3
from eth_account import Account as EvmAccount

from config import RPC, TOKENS, MAX_CONTINUOUS_TRANS


class Account:
    def __init__(self, private_key: str):
        self.key = private_key
        self.account = EvmAccount.from_key(private_key)
        self.address = Web3.to_checksum_address(self.account.address)
        self.db = dict()
        self.progress = dict()
        self.w3 = Web3(Web3.HTTPProvider(RPC))

    def init_db(self, db):
        self.db = db
        self.progress = db[self.address]

    def save_db(self):
        if self.progress['transactions'] <= 0:
            del self.db[self.address]
        else:
            self.db[self.address] = self.progress

        with open('data/db.json', 'w') as file:
            json.dump(self.db, file, indent='\t')

    def check_enough_fee(self) -> bool:
        fee = self.w3.eth.gas_price * 1000000
        return fee < self.get_native_balance()

    def get_native_balance(self) -> int:
        wei_balance = self.w3.eth.get_balance(self.address)
        balance = int(wei_balance / 10 ** 18)
        return wei_balance

    def get_token_data(self, token_address: str) -> dict:
        token = self.w3.eth.contract(
            address=Web3.to_checksum_address(token_address),
            abi=json.load(open('ABIs/erc20_abi.json'))
        )

        decimals = token.functions.decimals().call()
        balance_wei = token.functions.balanceOf(self.address).call()
        balance = balance_wei / 10 ** decimals

        return {'balance_wei': balance_wei, 'balance': balance, 'decimals': decimals}

    def get_token_balances(self) -> dict[str, int]:
        balances = dict()
        for symbol in ['usdc', 'usdt', 'busd']:
            balances[symbol] = self.get_token_data(TOKENS[symbol])['balance']

        return balances

    def get_max_balance_token(self) -> str:
        balances = self.get_token_balances()
        max_symbol = max(balances, key=balances.get)
        if balances[max_symbol] <= 0:
            return 'eth'
        return max_symbol

    def init_iters_per_dapps(self):
        transactions = self.progress['transactions']
        threshold = random.randint(10, 13)

        if transactions > threshold:
            transactions = threshold

        iters_per_dapps = []
        iters_per_dapp = random.randint(1, MAX_CONTINUOUS_TRANS) if transactions > MAX_CONTINUOUS_TRANS else random.randint(1, transactions)

        for i in range(transactions):
            summa = sum(iters_per_dapps)
            if summa > transactions:
                iters_per_dapps[-1] = iters_per_dapps[-1] - summa + transactions
            if sum(iters_per_dapps) == transactions:
                break
            iters_per_dapps.append(iters_per_dapp)

        return iters_per_dapps
