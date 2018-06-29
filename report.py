# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import os
import pymysql
import pywikibot

from queue import Queue
from threading import Lock, Thread

from pywikibot.bot import WikidataBot
from pywikibot.pagegenerators import (
    GeneratorFactory,
    PreloadingEntityGenerator,
)


class ReportingBot(WikidataBot):

    disambig_item = 'Q4167410'
    skip = {
        'brwiki',
        'enwiki',
        'hakwiki',
        'igwiki',
        'mkwiki',
        'mznwiki',
        'simplewikibooks',  # T180404
        'simplewikiquote',  # T180404
        'specieswiki',
        'towiki',
    }
    use_from_page = False

    def __init__(self, db, generator, **kwargs):
        self.availableOptions.update({
            'threads': 3,
        })
        super(ReportingBot, self).__init__(**kwargs)
        self.db = db
        self._generator = generator

    @property
    def generator(self):
        return PreloadingEntityGenerator(self._generator)

    def setup(self):
        super(ReportingBot, self).setup()
        count = self.getOption('threads')
        self.queue = Queue(count)
        self.workers = []
        for i in range(count):
            thread = Thread(target=self.work)
            thread.start()
            self.workers.append(thread)

    def work(self):
        while True:
            page, item = self.queue.get()
            if item is None:
                break
            self.process_page(page, item)
            self.queue.task_done()

    def is_disambig(self, item):
        for claim in item.claims.get('P31', []):
            if claim.target_equals(self.disambig_item):
                return True
        return False

    def treat_page_and_item(self, page, item):
        if not self.is_disambig(item):
            return
        for dbname in item.sitelinks:
            if dbname in self.skip:
                continue
            apisite = pywikibot.site.APISite.fromDBName(dbname)
            page = pywikibot.Page(apisite, item.sitelinks[dbname])
            self.queue.put((page, item))

    def process_page(self, page, item):
        with self.db.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute('SELECT id, page, stamp, status '
                        'FROM disambiguations WHERE item = %s AND wiki = %s',
                        (item.getID(), page.site.dbName()))
            data = cur.fetchone()

        if not page.exists():
            status = 'DELETED'
        elif page.isRedirectPage():
            status = 'REDIRECT'
        elif not page.isDisambig():
            status = 'READY'
        else:
            status = 'FALSE'

        ok = 0
        if data:
            page_eq = data['page'] == page.title(withNamespace=True)
            status_eq = data['status'] == status
            if page_eq and status_eq:
                return
            with self.db.cursor() as cur:
                ok += cur.execute('DELETE FROM disambiguations WHERE id = %s',
                                  (data['id'],))

        if status != 'FALSE':
            new = [item.getID(), page.site.dbName(),
                   page.title(withNamespace=True), status,
                   self.repo.username()]
            with self.db.cursor() as cur:
                ok += cur.execute(
                    'INSERT INTO disambiguations '
                    '(item, wiki, page, status, author) '
                    'VALUES (%s, %s, %s, %s, %s)', new)
        if ok:
            self.db.commit()

    def teardown(self):
        count = len(self.workers)
        for i in range(count):
            self.queue.put((None, None))
        for worker in self.workers:
            worker.join()
        super(ReportingBot, self).teardown()


def main(*args):
    options = {}
    local_args = pywikibot.handle_args(args)
    genFactory = GeneratorFactory()
    for arg in local_args:
        if genFactory.handleArg(arg):
            continue
        if arg.startswith('-'):
            arg, sep, value = arg.partition(':')
            if value != '':
                options[arg[1:]] = int(value) if value.isdigit() else value
            else:
                options[arg[1:]] = True

    db = pymysql.connect(
        database='s53728__data',
        host='tools.db.svc.eqiad.wmflabs',
        read_default_file=os.path.expanduser('~/replica.my.cnf'),
        charset='utf8mb4',
    )
    generator = genFactory.getCombinedGenerator()
    bot = ReportingBot(db, generator=generator, **options)
    bot.run()


if __name__ == '__main__':
    main()
