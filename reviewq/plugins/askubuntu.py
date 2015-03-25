import transaction
import datetime

from ..models import (
    DBSession,
    Source,
    User,
    Review,
    ReviewVote,
)

from ..helpers import (
    create_user,
    create_series,
    determine_sentiment,
    create_vote,
    get_lp
)

import stackexchange

from ..plugin import SourcePlugin


class AskUbuntu(SourcePlugin):
    def __init__(self, log=None):
        self.au = stackexchange.Site(stackexchange.AskUbuntu)
        super(AskUbuntu, self).__init__(log)

    def ingest(self, person=None):
        self.get_questions()

    def get_questions(self):
        qs = self.au.search(tagged=['juju', 'maas', 'openstack', 'landscape'])

        for q in qs:
                r = DBSession.query(Review).filter_by(api_url=q.url).first()
                if not r:
                    self.create(q)
                else:
                    self.refresh(q)

    def get_bugs(self):
        charm = self.lp.distributions['charms']
        branch_filter = "Show only Bugs with linked Branches"
        #branch_filter = 'Show all bugs'
        tasks = charm.searchTasks(linked_branches=branch_filter,
                                  tags=['-not-a-charm'],
                                  status=['New', 'Incomplete', 'Opinion',
                                          "Won't Fix", 'Confirmed', 'Triaged',
                                          'In Progress', 'Fix Committed',
                                          'Fix Released', 'Invalid',
                                          'Incomplete (with response)',
                                          'Incomplete (without response)'])
        for task in tasks:
            if '+source' in task.web_link:
                continue
            r = DBSession.query(Review).filter_by(api_url=task.self_link).first()
            if not r:
                self.create_from_bug(task)

    def create(self, question):
        with transaction.manager:
            r = DBSession.query(Review).filter_by(api_url=question.url).first()

            if not r:
                r = Review(api_url=question.url, created=question.creation_date)

            r.category = DBSession.query(Source).filter_by(slug='askubuntu').one()

    def create_from_merge(self, task):
        active = True
        with transaction.manager:
            r = DBSession.query(Review).filter_by(api_url=task.self_link).first()

            if not r:
                r = Review(type='UPDATE', api_url=task.self_link,
                           created=task.date_created.replace(tzinfo=None))
                DBSession.add(r)

            self.log(task)
            title = task.source_branch.display_name
            r.url = task.web_link
            r.title = title
            prevstate = r.state
            r.state = map_lp_state(task.queue_status)
            r.owner = create_user(task.registrant)
            r.source = DBSession.query(Source).filter_by(slug='lp').one()
            r.syncd = datetime.datetime.utcnow()

            if task.target_branch.sourcepackage:
                series_data = task.target_branch.sourcepackage.distroseries
                r.series = create_series(series_data)
                active = r.series.active

            if r.series and not r.series.active:
                r.state = 'ABANDONDED'

            comments = task.all_comments

            prev = r.updated
            if len(comments) > 0:
                comment = comments[len(comments)-1]
                r.updated = comment.date_created.replace(tzinfo=None)
            else:
                r.updated = task.date_created.replace(tzinfo=None)

            if r.updated != prev or r.state != prevstate:
                r.unlock()

            if r.state in ['REVIEWED', 'CLOSED'] and len(comments) > 0:
                if comments[len(comments)-1].author == task.registrant:
                    r.state = 'FOLLOW UP'

            DBSession.add(r)

        if active:
            self.parse_comments(comments, r)
        else:
            self.log("Old ass shit, skipping")

    def create_from_bug(self, task):
        bug = task.bug
        prev = None
        with transaction.manager:
            r = DBSession.query(Review).filter_by(api_url=task.self_link).first()
            if not r:
                r = Review(type='NEW', api_url=task.self_link,
                           created=task.date_created.replace(tzinfo=None))
            else:
                prev = r

            self.log(task)
            r.title = bug.title
            r.owner = create_user(task.owner)
            r.url = task.web_link
            r.state = bug_state(task)
            r.updated = (bug.date_last_message.replace(tzinfo=None)
                         if bug.date_last_message > bug.date_last_updated
                         else bug.date_last_updated.replace(tzinfo=None))

            if prev:
                if r.updated != prev.updated or r.state != prev.state:
                    r.unlock()

            r.source = DBSession.query(Source).filter_by(slug='lp').one()
            r.syncd = datetime.datetime.utcnow()

            if r.state in ['REVIEWED', 'CLOSED']:
                if bug.messages[len(bug.messages)-1].owner == task.assignee:
                    r.state = 'FOLLOW UP'
            if 'not-a-charm' in bug.tags:
                r.state = 'ABANDONDED'

            DBSession.add(r)

        self.parse_messages(bug.messages, r)

    def parse_comments(self, comments, review):
        for m in comments:
            rv = (DBSession.query(ReviewVote)
                         .filter_by(comment_id=m.self_link)).first()

            if rv and rv.created:
                self.log(m.self_link)
                continue

            vote = dict(vote=determine_sentiment(m.vote),
                        owner=create_user(m.author),
                        review=review,
                        comment_id=m.self_link,
                        created=m.date_created.replace(tzinfo=None),
                       )

            with transaction.manager:
                create_vote(vote)

    def parse_messages(self, comments, review):
        first = True
        for m in comments:
            if first:
                first = False  # WTF
                continue
            rv = (DBSession.query(ReviewVote)
                           .filter_by(comment_id=m.self_link)
                           .first()
                 )

            if rv and rv.created:
                self.log(m.self_link)
                continue

            vote = dict(vote=determine_sentiment(m.content),
                        owner=create_user(m.owner),
                        review=review,
                        comment_id=m.self_link,
                        created=m.date_created.replace(tzinfo=None),
                       )

            with transaction.manager:
                create_vote(vote)

    def refresh(self, record=None, id=None):
        if not record and not id:
            raise Exception('Need something to refresh')

        if not record:
            record = DBSession.query(Review).get(id)

        if not record.api_url:
            return False

        try:
            task = self.lp.load(record.api_url)
        except errors.NotFound:
            # It was deleted, or something
            record.status='ABANDONDED'
            DBSession.add(record)
            transaction.commit()
            return
        except ValueError:
            record.status='CLOSED'
            DBSession.add(record)
            transaction.commit()
            return

        if record.type == 'NEW':
            self.create_from_bug(task)
        elif record.type == 'UPDATE':
            self.create_from_merge(task)
            pass
        else:
            raise Exception('Turn down for what')
