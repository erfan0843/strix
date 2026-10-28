import sys
sys.path.insert(0, '<nora-ui>')
from backend.captcha import verify_captcha
pepper = open('<pepper file, local only>').read().strip()
token = sys.argv[1]
for n in range(10000):
    a = f"{n:04d}"
    if verify_captcha(pepper, token, a):
        print(a); break
else:
    print(''); sys.exit(1)
