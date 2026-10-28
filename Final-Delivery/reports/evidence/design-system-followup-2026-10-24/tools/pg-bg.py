import pgserver, time, sys
srv = pgserver.get_server('<local> cleanup_mode=None)
print(srv.get_uri(), flush=True)
while True: time.sleep(60)
