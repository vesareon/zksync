import json
import time
import random
from web3 import Web3

from src.account import Account
from config import SPACEFI_DEPOSIT, SYNCSWAP_DEPOSIT, GAS_THRESHOLD


def get_accounts(path: str) -> list[Account]:
    with open(path, 'r') as keys_file:
        accounts = [Account(line.replace("\n", "")) for line in keys_file.readlines()]
    return accounts


def save_db(db):
    with open('data/db.json', 'w') as file:
        json.dump(db, file, indent='\t')


def create_db(accounts: list[Account], transactions: list[int], volumes: bool, bridge: bool) -> dict[str, dict[str, int]]:
    db = dict()

    for account in accounts:
        wallet_info = {
            "bridge": bridge,
            "volumes": volumes,
            "transactions": random.randint(*transactions),
            "spacefi_deposit": random.randint(*SPACEFI_DEPOSIT),
            "syncswap_deposit": random.randint(*SYNCSWAP_DEPOSIT)
        }

        db[account.address] = wallet_info

    with open('data/db.json', 'w') as file:
        json.dump(db, file, indent='\t')

    return db


def check_allowance(chain, token, address, router_address, amount, key):
    allowance = token.functions.allowance(address, router_address).call()
    # coef = random.choice([1, random.randint(5, 10)])
    if allowance < amount:
        approve_txn = token.functions.approve(router_address, amount).build_transaction({
            'from': address,
            'gas': 0,
            'gasPrice': chain.eth.gas_price,
            'nonce': chain.eth.get_transaction_count(address)
        })
        approve_txn['gas'] = chain.eth.estimate_gas(approve_txn)

        signed_approve_txn = chain.eth.account.sign_transaction(approve_txn, key)
        approve_txn_hash = chain.eth.send_raw_transaction(signed_approve_txn.rawTransaction)
        chain.eth.wait_for_transaction_receipt(approve_txn_hash, timeout=300)
        time.sleep(random.randint(15, 20))


def value_for_logs(token: str, amount: int) -> str:
    decimals = {'usdc': 6, 'usdt': 6, 'busd': 18}
    if token == 'eth':
        return f"{round(Web3.from_wei(amount, 'ether'), 4)} {token}"
    else:
        return f"{round(amount / 10 ** decimals[token], 2)} {token}"
