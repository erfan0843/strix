"""Mechanical token mapping (design system v3). Usage: python3 ds-map.py <nora-ui dir> [--dry]"""
import re, sys, os, collections
root=sys.argv[1]; dry='--dry' in sys.argv
CSS=[f for f in os.listdir(root) if f.endswith('.css') and f!='glass.css']
HTML=['home.html','event.html','form.html','create.html','builder.html','post.html','events.html']
def fs_tok(v):
    v=float(v)
    if v<9 or v>60: return None
    steps=[(11,'--fs-micro'),(12,'--fs-cap'),(13.5,'--fs-sub'),(15,'--fs-body'),(16.5,'--fs-head'),(18,'--fs-lead'),(20,'--fs-title'),(24,'--fs-kpi'),(27,'--fs-display'),(32,'--fs-hero-m'),(42,'--fs-hero')]
    return min(steps,key=lambda s:(abs(s[0]-v),-s[0]))[1]
def r_tok(v):
    if v in('99','999'): return '--r-pill'
    v=float(v)
    if v<6: return None
    steps=[(8,'--r-xs'),(12,'--r-sm'),(16,'--r-md'),(22,'--r-lg'),(28,'--r-xl')]
    if v>34: return None
    return min(steps,key=lambda s:(abs(s[0]-v),-s[0]))[1]
def sp_tok(v):
    v=float(v)
    if v<3 or v>44: return None
    steps=[(4,'--sp-1'),(6,'--sp-1h'),(8,'--sp-2'),(10,'--sp-2h'),(12,'--sp-3'),(16,'--sp-4'),(20,'--sp-5'),(24,'--sp-6'),(32,'--sp-8'),(40,'--sp-10')]
    return min(steps,key=lambda s:(abs(s[0]-v),-s[0]))[1]
stats=collections.Counter(); detail=collections.defaultdict(collections.Counter)
def map_css(txt,name):
    def f1(m):
        t=fs_tok(m.group(2))
        if not t: return m.group(0)
        stats[name+':fs']+=1; detail['fs'][m.group(2)+'->'+t]+=1; return f"{m.group(1)}var({t})"
    txt=re.sub(r'(font-size:\s*)([0-9.]+)px(?=[;}! ])',f1,txt)
    def f2(m):
        t=r_tok(m.group(2))
        if not t: return m.group(0)
        stats[name+':r']+=1; detail['r'][m.group(2)+'->'+t]+=1; return f"{m.group(1)}var({t})"
    txt=re.sub(r'(border-radius:\s*)([0-9.]+)px(?=[;}!])',f2,txt)
    def f3(m):
        t=sp_tok(m.group(3))
        if not t: return m.group(0)
        stats[name+':gap']+=1; detail['gap'][m.group(3)+'->'+t]+=1; return f"{m.group(1)}{m.group(2)}var({t})"
    txt=re.sub(r'((?:row-|column-)?)(gap:\s*)([0-9.]+)px(?=[;}!])',f3,txt)
    return txt
for f in CSS:
    p=os.path.join(root,f); s=open(p,encoding='utf-8').read(); n=map_css(s,f)
    if n!=s and not dry: open(p,'w',encoding='utf-8').write(n)
for f in HTML:
    p=os.path.join(root,f)
    if not os.path.exists(p): continue
    s=open(p,encoding='utf-8').read()
    n=re.sub(r'(<style[^>]*>)(.*?)(</style>)',lambda m:m.group(1)+map_css(m.group(2),f)+m.group(3),s,flags=re.S)
    if n!=s and not dry: open(p,'w',encoding='utf-8').write(n)
for k,v in sorted(stats.items()): print(k,v)
for kind in('fs','r','gap'): print(kind,dict(sorted(detail[kind].items(),key=lambda x:-x[1])))
