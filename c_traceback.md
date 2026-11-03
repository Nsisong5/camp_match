
I am getting this when i have run the script for the messaging relay outbox and I have sent multiple messages to the user


{
  "items": [],
  "total": 0,
  "page": 1,
  "page_size": 20
}


do not write a single line of code yet but diagnose the problem and report it to me


below is the log I got from running the messaging outbox script




(myweasyprintenv) root@localhost:/sdcard/camp_match# cd scripts
(myweasyprintenv) root@localhost:/sdcard/camp_match/scripts# die
bash: die: command not found
(myweasyprintenv) root@localhost:/sdcard/camp_match/scripts# python run_messaging_outbox_relay.py
2026-11-01 22:59:56 [info     ] domain_event_published         event_id=06e56abf-c709-4db6-a0d7-f629717e444b event_type=MessageCreated
2026-11-01 22:59:56 [info     ] notification_event_received    event_id=06e56abf-c709-4db6-a0d7-f629717e444b event_type=MessageCreated
2026-11-01 22:59:56 [warning  ] notification_event_rejected    error='Unsupported event type: MessageCreated' event_id=06e56abf-c709-4db6-a0d7-f629717e444b
2026-11-01 22:59:56 [info     ] domain_event_published         event_id=9a1a643e-495a-4738-a2b9-6240666b8898 event_type=MessageCreated
2026-11-01 22:59:56 [info     ] notification_event_received    event_id=9a1a643e-495a-4738-a2b9-6240666b8898 event_type=MessageCreated
2026-11-01 22:59:56 [warning  ] notification_event_rejected    error='Unsupported event type: MessageCreated' event_id=9a1a643e-495a-4738-a2b9-6240666b8898
2026-11-01 22:59:56 [info     ] domain_event_published         event_id=cade466c-2a60-466a-9db0-53cd97f2e3f0 event_type=MessageCreated
2026-11-01 22:59:56 [info     ] notification_event_received    event_id=cade466c-2a60-466a-9db0-53cd97f2e3f0 event_type=MessageCreated
2026-11-01 22:59:56 [warning  ] notification_event_rejected    error='Unsupported event type: MessageCreated' event_id=cade466c-2a60-466a-9db0-53cd97f2e3f0
2026-11-01 22:59:56 [info     ] domain_event_published         event_id=1b3ce902-f3f5-4641-ad02-7d64a7e64271 event_type=MessageCreated
2026-11-01 22:59:56 [info     ] notification_event_received    event_id=1b3ce902-f3f5-4641-ad02-7d64a7e64271 event_type=MessageCreated
2026-11-01 22:59:57 [warning  ] notification_event_rejected    error='Unsupported event type: MessageCreated' event_id=1b3ce902-f3f5-4641-ad02-7d64a7e64271
Messaging Outbox Relay: claimed=4, dispatched=4, failed=0
(myweasyprintenv) root@localhost:/sdcard/camp_match/scripts# cd ..
(myweasyprintenv) root@localhost:/sdcar