# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import os
import pymysql
import pywikibot

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
        super(ReportingBot, self).__init__(**kwargs)
        self.db = db
        self._generator = generator

    @property
    def generator(self):
        return PreloadingEntityGenerator(self._generator)

    def is_disambig(self, item):
        for claim in item.claims.get('P31', []):
            if claim.target_equals(self.disambig_item):
                return True
        return False

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


class GeneratorBot(ReportingBot):

    def treat_page_and_item(self, page, item):
        if not self.is_disambig(item):
            return
        for dbname in item.sitelinks:
            if dbname in self.skip:
                continue
            site = pywikibot.site.APISite.fromDBName(dbname)
            page = pywikibot.Page(site, item.sitelinks[dbname])
            self.process_page(page, item)


class WikiUpdatingBot(ReportingBot):

    def __init__(self, db, wiki, **kwargs):
        super(WikiUpdatingBot, self).__init__(db, **kwargs)
        self.wiki = wiki

    def setup(self):
        super(WikiUpdatingBot, self).setup()
        with self.db.cursor() as cur:
            cur.execute('SELECT item WHERE wiki = %s', (self.wiki,))
            data = cur.fetchall()
        self._generator = (pywikibot.ItemPage(self.repo, item)
                           for (item,) in data)

    def treat_page_and_item(self, page, item):
        link = item.sitelinks.get(self.wiki)
        if not link or not self.is_disambig(item):
            with self.db.cursor() as cur:
                cur.execute('DELETE FROM disambiguations WHERE wiki = %s '
                            'AND item = %s', (self.wiki, item.getID()))
                self.db.commit()
            return

        site = pywikibot.site.APISite.fromDBName(self.wiki)
        page = pywikibot.Page(site, link)
        self.process_page(page, item)


def main(*args):
    options = {}
    local_args = pywikibot.handle_args(args)
    genFactory = GeneratorFactory()
    cls = GeneratorBot
    for arg in local_args:
        if genFactory.handleArg(arg):
            continue
        if arg.startswith('-'):
            arg, sep, value = arg.partition(':')
            if value != '':
                options[arg[1:]] = int(value) if value.isdigit() else value
            else:
                options[arg[1:]] = True
        else:
            options['wiki'] = arg
            cls = WikiUpdatingBot

    db = pymysql.connect(
        database='s53728__data',
        host='tools.db.svc.eqiad.wmflabs',
        read_default_file=os.path.expanduser('~/replica.my.cnf'),
        charset='utf8mb4',
    )
    generator = genFactory.getCombinedGenerator()
    bot = cls(db, generator=generator, **options)
    bot.run()


if __name__ == '__main__':
    main()
