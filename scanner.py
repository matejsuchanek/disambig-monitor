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
        'simplewikibooks',  # T180404
        'simplewikiquote',  # T180404
    }
    use_from_page = None

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
        with self.db.cursor() as cur:
            cur.execute('SELECT wiki, id FROM disambiguations WHERE item = %s',
                        (item.getID(),))
            data = dict(cur.fetchall())
        if item.isRedirectPage() or not self.is_disambig(item):
            if data:
                with self.db.cursor() as cur:
                    cur.execute('DELETE FROM disambiguations WHERE item = %s',
                                (item.getID(),))
                self.db.commit()
            return

        remove = set(data) - set(item.sitelinks)
        if remove:
            with self.db.cursor() as cur:
                cur.execute('DELETE FROM disambiguations WHERE id IN (%s)'
                            % ','.join(str(data[wiki]) for wiki in remove))
            self.db.commit()

        for dbname in item.sitelinks:
            if dbname in self.skip:
                continue
            site = pywikibot.site.APISite.fromDBName(dbname)
            page = pywikibot.Page(site, item.sitelinks[dbname])
            self.process_page(page, item)


class DatabaseUpdatingBot(ReportingBot):

    def setup(self):
        super(DatabaseUpdatingBot, self).setup()
        self._generator = self.generate_items()

    def generate_items(self, wiki=None):
        last_id = 0
        while True:
            query = 'SELECT id, item FROM disambiguations WHERE'
            args = []
            if wiki:
                query += ' wiki = %s AND'
                args.append(wiki)
            query = ' id > %d ORDER BY id LIMIT 100'
            args.append(last_id)
            with self.db.cursor() as cur:
                cur.execute(query, args)
            data = cur.fetchall()
            buffer = set()
            for id_, item in data:
                buffer.add(pywikibot.ItemPage(self.repo, item))
                last_id = id_
            if not buffer:
                break
            for item in buffer:
                yield item

    def process_link(self, item, wiki):
        link = item.sitelinks.get(wiki)
        if not link or not self.is_disambig(item):
            with self.db.cursor() as cur:
                cur.execute('DELETE FROM disambiguations WHERE wiki = %s '
                            'AND item = %s', (wiki, item.getID()))
            self.db.commit()
            return

        site = pywikibot.site.APISite.fromDBName(wiki)
        page = pywikibot.Page(site, link)
        self.process_page(page, item)

    def treat_page_and_item(self, page, item):
        for wiki in item.sitelinks:
            self.process_link(item, wiki)


class SingleWikiUpdatingBot(DatabaseUpdatingBot):

    def __init__(self, db, wiki, **kwargs):
        super(SingleWikiUpdatingBot, self).__init__(db, **kwargs)
        self.wiki = wiki

    def generate_items(self):
        return self.generate_items(self.wiki)

    def treat_page_and_item(self, page, item):
        self.process_item(item, self.wiki)


def main(*args):
    options = {}
    local_args = pywikibot.handle_args(args)
    site = pywikibot.Site()
    genFactory = GeneratorFactory(site=site)
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

    db = pymysql.connect(
        database='s53728__data',
        host='tools.db.svc.eqiad.wmflabs',
        read_default_file=os.path.expanduser('~/replica.my.cnf'),
        charset='utf8mb4',
    )
    generator = genFactory.getCombinedGenerator()
    if generator:
        cls = GeneratorBot
    elif options.get('wiki'):
        cls = SingleWikiUpdatingBot
    else:
        cls = DatabaseUpdatingBot
    bot = cls(db, generator=generator, **options)
    bot.run()


if __name__ == '__main__':
    main()
