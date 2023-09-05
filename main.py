import sys
import time
import json
import random
from loguru import logger as logging
from web3 import Web3
from web3.middleware import geth_poa_middleware

from src.runner import Runner
from config import SLEEP_WALLETS
from src.utils import get_accounts, create_db

logging.remove()
logging.add(sys.stderr, format="<white>{time:HH:mm:ss}</white> | <level>{level: <2}</level> | <level>{message}</level>")


def options():
    while True:
        print('Выберите стратегию:')
        print('1. Официальный мост и прогрев')
        print('2. Прогрев')
        print('3. Набив объемов', end='\n\n')

        try:
            strategy = int(input('Введите номер стратегии: '))
        except ValueError:
            continue

        if strategy == 1:
            bridge, volumes = True, False
        elif strategy == 2:
            bridge, volumes = False, False
        elif strategy == 3:
            bridge, volumes = False, True
        else:
            continue

        try:
            min_transactions = int(input('Минимальное кол-во транзакций: '))
            max_transactions = int(input('Максимальное кол-во транзакций: '))

            if max_transactions < min_transactions:
                continue
        except ValueError:
            continue

        return [min_transactions, max_transactions], volumes, bridge


def main():
    ether = Web3(Web3.HTTPProvider("https://eth.llamarpc.com"))
    ether.middleware_onion.inject(geth_poa_middleware, layer=0)
    accounts = get_accounts('data/keys.txt')

    if not accounts:
        logging.error("Добавьте приватные ключи в файл data/keys.txt")
        return

    db = json.load(open('data/db.json'))
    if len(db) == 0:
        db = create_db(accounts, *options())
        print('База данных создана!', end='\n\n')
    else:
        print(f'Прогнано {len(accounts) - len(db)} из {len(accounts)} кошельков', end='\n\n')
        print('1. Продолжить прогон')
        print('2. Создать новую базу данных', end='\n\n')
        selection = int(input('Выберите номер действия: '))
        print()
        if selection == 2:
            create_db(accounts, *options())
            print('База данных создана!', end='\n\n')

    while len(db) != 0:
        random.shuffle(accounts)
        for account in accounts:
            if account.address not in db:
                continue
            account.init_db(db)
            Runner(account).start()
            time.sleep(random.randint(*SLEEP_WALLETS))


if __name__ == '__main__':
    main()
