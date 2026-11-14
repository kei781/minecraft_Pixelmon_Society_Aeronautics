from __future__ import annotations
import argparse
import json
import logging
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description='PSA support bot and trusted operator commands')
    parser.add_argument('--config', type=Path, default=Path('config.json'))
    sub = parser.add_subparsers(dest='command',required=True)
    sub.add_parser('run')
    sub.add_parser('check')
    snapshot = sub.add_parser('snapshot')
    snapshot.add_argument('--server',type=Path,required=True)
    snapshot.add_argument('--notes',type=Path)
    snapshot.add_argument('--output',type=Path,required=True)
    search = sub.add_parser('search'); search.add_argument('query')
    tickets = sub.add_parser('tickets'); tickets.add_argument('--all',action='store_true')
    update = sub.add_parser('update')
    update.add_argument('ticket',type=int)
    update.add_argument('--status',choices=['investigating','needs_information','resolved','not_a_bug'],required=True)
    update.add_argument('--result-file',type=Path,required=True,
                        help='JSON with player-facing summary and private evidence; no shell interpolation')
    args = parser.parse_args()
    os.umask(0o077)
    if args.command == 'snapshot':
        from .snapshot import build_snapshot
        data = build_snapshot(args.server,args.notes)
        args.output.parent.mkdir(parents=True,exist_ok=True)
        temp = args.output.with_suffix('.tmp')
        temp.write_text(json.dumps(data,ensure_ascii=False))
        temp.replace(args.output)
        print(json.dumps({'snapshot_id':data['manifest']['snapshot_id'],
                          'documents':len(data['documents']),'files':len(data['manifest']['files'])}))
        return
    from .config import Config
    from .knowledge import Knowledge
    from .store import Store
    cfg = Config.load(args.config)
    if args.command == 'check':
        knowledge = Knowledge(cfg.knowledge)
        print(json.dumps({'config_valid':True,'documents':len(knowledge.documents),
                          'snapshot_id':knowledge.manifest['snapshot_id'],
                          'credentials_present': {key:bool(os.environ.get(key)) for key in
                                                  ('DISCORD_BOT_TOKEN',)}}))
        return
    if args.command == 'search':
        print(json.dumps(Knowledge(cfg.knowledge).search([args.query]),ensure_ascii=False,indent=2))
        return
    if args.command in ('tickets','update'):
        store = Store(cfg.database)
        store.bind(cfg)
        if args.command == 'tickets':
            print(json.dumps(store.tickets(args.all),ensure_ascii=False,indent=2))
        else:
            result = json.loads(args.result_file.read_text())
            store.update_ticket(args.ticket,args.status,result['summary'],result['evidence'])
            print(json.dumps({'ticket':args.ticket,'status':args.status}))
        return
    for key in ('DISCORD_BOT_TOKEN',):
        if not os.environ.get(key):
            parser.error(f'{key} is not configured')
    from .bot import SupportBot
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(name)s %(levelname)s %(message)s')
    # Provider request/response logs are not enabled.
    logging.getLogger('httpx').setLevel(logging.WARNING)
    bot = SupportBot(cfg)
    bot.run(os.environ['DISCORD_BOT_TOKEN'],log_handler=None)


if __name__ == '__main__':
    main()
