# -*- coding:utf-8 -*-
import MySQLdb
import config
import uuid
import cStringIO

'''
Q: 这个脚本都做了什么呀？
A: 它把老的数据库转换成了新的数据库？

Q: 它都做了哪些转换呀？
A: 它转换了用户，版面，帖子，楼，楼中楼和站内信，
   然后链接的转换也是很大的。

Q: 用户怎么转的呀？
A: 老的用户表叫 userinfo，新的叫 users。
   没有什么特别要说的，除了我规定 gender 男生是 1 女生是 0。

Q: 版面怎么转的呀？
A: 自己看吧～

Q: 帖子怎么转的呀？
A: 新 tid 是按老 (bid, tid) 排序后重新编的。
   这里有个坑，就是老的 timestamp（最后更新） 是 unix 时间戳，
   我直接用了 from_unixtime 把它转成 MySQL 中的 datetime，
   可能会损失精度或者需要考虑时区问题。

Q: 楼怎么转的呀？
A: 新 pid 是按老 (bid, tid, pid) 排序后重新编的。
   这里也有坑，坑 1 是两个时间的处理有上一条里说的问题。
   坑 2 是帖子签名档原来存的是“引用”现在直接存内容了，
   坑 3 是 parse_type 现在取值 'html' 或 'plain'。

Q: 楼中楼怎么转的呀？
A: 无可奉告！

Q: 站内信怎么转的呀？
A: 发送者不是 system 的认为是站内信。时间方面有前述的坑。

Q: 嗯好像大部分问题都问完了，然后就剩你说的很大那个，
   链接作了哪些替换？
A: 哦这个呀，我们现在做的就是把以下四种格式的链接换成新链接：
   http://www.chexie.net/bbs/content/?bid=<bid>&tid=<tid>[&p=<p>]
   http://chexie.net/bbs/content/?bid=<bid>&tid=<tid>[&p=<p>]
   http://www.chexie.net/cgi-bin/bbs.pl?see=<see>&b=<b>[&p=<p>]
   http://chexie.net/cgi-bin/bbs.pl?see=<see>&b=<b>[&p=<p>]
   新链接格式是 /thread/<new_tid>/[page/<p>/]

Q: 嗯好吧好像没什么问题了，中秋快乐 ^_^
A: 很惭愧，做了一些微小的工作，谢谢大家 Θ..Θ
'''

db = MySQLdb.connect(host=config.DB_SERVER, passwd=config.DB_PASSWORD, db=config.DB_NAME, user=config.DB_USERNAME)

c = db.cursor()

c.execute("""insert into users(username, password, gender, avatar, intro, sig1, sig2, sig3, hobby, qq, mail, registration_date, last_login_time, num_post, num_reply, num_water, num_sign, current_board, user_agent) select username, password, sex = "男", icon, intro, sig1, sig2, sig3, hobby, qq, mail, regdate, lastdate, post, reply, water, sign, nowboard, logininfo from capubbs.userinfo""")

c.execute("""insert into boards(bid, name, invisible) select bid, bbstitle, hide from capubbs.boardinfo""")

c.execute("""alter table capubbs.threads add column new_tid integer""")
c.execute("""update capubbs.threads, (select bid, tid, @cur_tid := if(@cur_tid is null, 1, @cur_tid + 1) as new_tid from capubbs.threads order by bid, tid) as ord set threads.new_tid = ord.new_tid where threads.bid = ord.bid and threads.tid = ord.tid""")
c.execute("""insert into Threads(tid, author_uid, bid, title, replyer_uid, num_click, num_reply, good, sticky, created_at, replied_at) select new_tid, author.uid, bid, title, replier.uid, click, threads.reply, threads.extr, top, postdate, from_unixtime(timestamp) from (capubbs.threads as threads join users as author on threads.author = author.username) left join users as replier on replyer = replier.username""")

c.execute("""alter table capubbs.posts add column new_pid integer""")
c.execute("""update capubbs.posts, (select bid, tid, pid, @cur_pid := if(@cur_pid is null, 1, @cur_pid + 1) as new_pid from capubbs.posts order by bid, tid, pid) as ord set posts.new_pid = ord.new_pid where posts.bid = ord.bid and posts.tid = ord.tid and posts.pid = ord.pid""")
c.execute("""insert into posts(pid, uid, bid, tid, title, content, created_at, updated_at, signature, ip, parse_type) select new_pid, author.uid, posts.bid, threads.new_tid, posts.title, text, from_unixtime(replytime), from_unixtime(updatetime), case posts.sig when 1 then author.sig1 when 2 then author.sig2 when 3 then author.sig3 end, ip, case ishtml when 'YES' then 'html' else 'plain' end from capubbs.posts join users as author on posts.author = author.username join capubbs.threads on threads.bid = posts.bid and threads.tid = posts.tid""")

c.execute("""insert into comments(cid, pid, uid, content, time, deleted) select lzl.id, posts.new_pid, users.uid, lzl.text, from_unixtime(time), !lzl.visible from capubbs.lzl join capubbs.posts on lzl.fid = posts.fid join users on lzl.author = users.username""")

c.execute("""insert into messages(mid, sender_uid, receiver_uid, content, time, is_read, sender_deleted, receiver_deleted) select id, sender.uid, receiver.uid, text, from_unixtime(time), hasread, 0, 0 from capubbs.messages join users as sender on messages.sender = sender.username join users as receiver on messages.receiver = receiver.username where sender != 'system'""")

#c.execute("""insert into notifications(nid, uid, time, type, pid, is_read) select id, receiver.uid, from_unixtime(time), case messages.text when 'reply' then 1 when 'at' then 2 when 'replylzl' then 3 when 'replylzlreply' then 4 when 'quote' then 5 end, new_pid, hasread from capubbs.messages join users as receiver on messages.receiver = receiver.username join capubbs.posts on messages.rbid = posts.bid and messages.rtid = posts.tid where sender = 'system'""")

c.close()


c2 = db.cursor()
c3 = db.cursor()

def parse_args(s, pos, begin):
    stat = 'k'
    d = {}
    k = ''
    v = ''
    while True:
        if pos >= len(s):
            d[k] = v
            break
        nxt = s[pos]
        pos += 1
        if stat == 'k':
            if nxt.isalnum() or nxt == '_':
                k += nxt
            elif nxt == '=':
                stat = 'v'
            else:
                break
                raise KeyError
        elif stat == 'v':
            if nxt.isalnum() or nxt == '_':
                v += nxt
            elif nxt == '&':
                if s[pos:pos + 4] == 'amp;':
                    pos += 4
                d[k] = v
                stat = 'k'
                k = ''
                v = ''
            else:
                d[k] = v
                break
    return (begin, pos, d)

def parse_url(s, pattern):
    res = []
    pos = s.find(pattern)
    if pos == -1:
        return None
    while pos != -1:
        res.append(parse_args(s, pos + len(pattern), pos))
        pos = s.find(pattern, pos + 1)
    return res

tbl_name = "tbl_" + uuid.uuid4().hex
c3.execute("""create table %s (bid integer, tid integer, n integer primary key auto_increment)""" % tbl_name)

def tihuan(pattern, proc):
    c2.execute("""select pid, content from posts where locate('%s', content) > 0 order by pid desc""" % pattern)
    res = c2.fetchall()
    actions = []
    lookups = []
    for x in res:
        ca = (x, parse_url(x[1], pattern))
        if ca[1] == None:
            actions.append(None)
        else:
            ca1 = []
            for y in ca[1]:
                p = proc(y[2])
                if p:
                    lookups.append(p)
                    ca1.append(y)
            actions.append((x, ca1))
    
    c3.executemany("""insert into """ + tbl_name + """(bid, tid) values (%s, %s)""", lookups)
    c3.execute("""select * from """ + tbl_name)
    c3.execute("""select capubbs.threads.new_tid, capubbs.threads.tid, capubbs.threads.bid, n from %s left join capubbs.threads on %s.bid = capubbs.threads.bid and %s.tid = capubbs.threads.tid order by n""" % (tbl_name, tbl_name, tbl_name))
    res = c3.fetchall()
    updates = []
    rc = 0
    for x in actions:
        last = 0
        o = cStringIO.StringIO()
        s = x[0][1]
        for a in x[1]:
            o.write(s[last:a[0]])
            o.write('/thread/')
            o.write(str(res[rc][0]))
            o.write('/')
            if 'p' in x[1][0][2]:
                o.write('page/')
                o.write(x[1][0][2]['p'])
                o.write('/')
            last = a[1] - 1
        o.write(s[last:])
        updates.append((o.getvalue(), x[0][0]))
        o.close()
    
    c3.executemany("""update posts set content = %s where pid = %s""", updates)

def decode26(s):
    return reduce(lambda tot, x: tot * 26 + ord(x) - ord('a'), s, 0) + 1

tihuan("""http://www.chexie.net/bbs/content/?""", lambda x: (x['bid'], x['tid']) if ('bid' in x) and ('tid' in x) else None)
tihuan("""http://chexie.net/bbs/content/?""", lambda x: (x['bid'], x['tid']) if ('bid' in x) and ('tid' in x) else None)
tihuan("""http://www.chexie.net/cgi-bin/bbs.pl?""", lambda x: (x['b'], decode26(x['see'])) if ('b' in x) and (x['b'] != '') and ('see' in x) else None)
tihuan("""http://chexie.net/cgi-bin/bbs.pl?""", lambda x: (x['b'], decode26(x['see'])) if ('b' in x) and (x['b'] != '') and ('see' in x) else None)
c3.execute("""drop table %s""" % tbl_name)
