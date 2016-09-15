use capuhome;

insert into users(username, password, gender, avatar, intro, sig1, sig2, sig3, hobby, qq, mail, registration_date, last_login_time, num_post, num_reply, num_water, num_sign, current_board, user_agent) select username, password, sex = "男", icon, intro, sig1, sig2, sig3, hobby, qq, mail, regdate, lastdate, post, reply, water, sign, nowboard, logininfo from capubbs.userinfo;

insert into boards(bid, name, invisible) select bid, bbstitle, hide from capubbs.boardinfo;

alter table capubbs.threads add column new_tid integer;
set @cur_tid = 0;
update capubbs.threads, (select bid, tid, @cur_tid := @cur_tid + 1 as new_tid from capubbs.threads order by bid, tid) as ord set threads.new_tid = ord.new_tid where threads.bid = ord.bid and threads.tid = ord.tid;
insert into Threads(tid, author_uid, bid, title, replyer_uid, num_click, num_reply, good, sticky, created_at, replied_at) select new_tid, author.uid, bid, title, replier.uid, click, threads.reply, threads.extr, top, postdate, from_unixtime(timestamp) from (capubbs.threads as threads join users as author on threads.author = author.username) left join users as replier on replyer = replier.username;

alter table capubbs.posts add column new_pid integer;
set @cur_pid = 0;
update capubbs.posts, (select bid, tid, pid, @cur_pid := @cur_pid + 1 as new_pid from capubbs.posts order by bid, tid, pid) as ord set posts.new_pid = ord.new_pid where posts.bid = ord.bid and posts.tid = ord.tid and posts.pid = ord.pid;
insert into posts(pid, uid, bid, tid, title, content, created_at, updated_at, signature, ip, parse_type) select new_pid, author.uid, posts.bid, threads.new_tid, posts.title, text, from_unixtime(replytime), from_unixtime(updatetime), case posts.sig when 1 then author.sig1 when 2 then author.sig2 when 3 then author.sig3 end, ip, case ishtml when 'YES' then 'html' else 'plain' end from capubbs.posts join users as author on posts.author = author.username join capubbs.threads on threads.bid = posts.bid and threads.tid = posts.tid;

insert into comments(cid, pid, uid, content, time, deleted) select lzl.id, posts.new_pid, users.uid, lzl.text, from_unixtime(time), !lzl.visible from capubbs.lzl join capubbs.posts on lzl.fid = posts.fid join users on lzl.author = users.username;

insert into messages(mid, sender_uid, receiver_uid, content, time, is_read, sender_deleted, receiver_deleted) select id, sender.uid, receiver.uid, text, from_unixtime(time), hasread, 0, 0 from capubbs.messages join users as sender on messages.sender = sender.username join users as receiver on messages.receiver = receiver.username where sender != 'system';

insert into notifications(nid, uid, time, type, pid, is_read) select id, receiver.uid, from_unixtime(time), case messages.text when 'reply' then 1 when 'at' then 2 when 'replylzl' then 3 when 'replylzlreply' then 4 when 'quote' then 5 end, new_pid, hasread from capubbs.messages join users as receiver on messages.receiver = receiver.username join capubbs.posts on messages.rbid = posts.bid and messages.rtid = posts.tid where sender = 'system';
