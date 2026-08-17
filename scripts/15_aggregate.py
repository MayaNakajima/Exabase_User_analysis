"""STEP 15: 月次推移・グループ×象限・過剰スペック等のクロス集計 → data/aggregates_all.json"""
import os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import DATA, OUTPUT
os.chdir(DATA)   # 相対パスの read/write は data/ に解決

import json
from collections import defaultdict, Counter
import statistics

conv=json.load(open('conversations_all.json',encoding='utf-8'))
cls=json.load(open('classification_all.json',encoding='utf-8'))
members=json.load(open('members.json',encoding='utf-8'))
rows=json.load(open('user_all.json',encoding='utf-8'))
meta=json.load(open('meta_all.json',encoding='utf-8'))
CATN=meta['cat_names']; GL=meta['grp_label']
ADV={'Deep Research (詳細)','文書検索 (RAG)','スライド作成 (PowerPoint)','ファイル出力 (Word、Excelなど)','ウェブリサーチ (高速)','国内記事検索','官公需案件検索','音声書き起こし','画像生成 (高性能, GPT-image)','画像生成 (高速, Nano Banana)','SharePointファイル検索','Teams検索','Outlookカレンダー予定確認','Box検索','ヘルプページ検索'}
SIMPLE={'C01','C02','C11','C12'}
def grp(email):
    m=members.get(email); return m['group'] if m else 'former'
def claude(email):
    m=members.get(email); return bool(m and m['claude'])
for c in conv: c['cat']=cls.get(c['conv_id'],'C12')

months=sorted({c['month'] for c in conv})
# monthly overall
M=defaultdict(lambda:{'convs':0,'msgs':0,'users':set(),'tier':Counter(),'adv':0,'cats':Counter(),'overspec':0,'toolconvs':0})
first_seen={}
for c in conv:
    m=M[c['month']]
    m['convs']+=1; m['msgs']+=c['user_msgs']+c['asst_msgs']; m['users'].add(c['user'])
    m['tier'][c['tier']]+=c['user_msgs']
    adv=any(t in ADV for t in c['tools'])
    if adv: m['adv']+=1
    if c['tools']: m['toolconvs']+=1
    m['cats'][c['cat']]+=1
    if c['tier'] in ('Standard','Premium') and not claude(c['user']) and c['cat'] in SIMPLE and c['user_msgs']<=2 and not adv:
        m['overspec']+=1
    fs=first_seen.get(c['user'])
    if fs is None or c['month']<fs: first_seen[c['user']]=c['month']
new_by_month=Counter(first_seen.values())
cum=set(); monthly=[]
for mo in months:
    d=M[mo]; cum|=d['users']
    tt=sum(d['tier'].values()) or 1
    monthly.append({'month':mo,'convs':d['convs'],'msgs':d['msgs'],'active_users':len(d['users']),
        'new_users':new_by_month.get(mo,0),'cum_users':len(cum),
        'eco':d['tier'].get('Economy',0),'std':d['tier'].get('Standard',0),'pre':d['tier'].get('Premium',0),
        'sp_share':round((d['tier'].get('Standard',0)+d['tier'].get('Premium',0))/tt*100,1),
        'adv_rate':round(d['adv']/d['convs']*100,1) if d['convs'] else 0,
        'tool_rate':round(d['toolconvs']/d['convs']*100,1) if d['convs'] else 0,
        'overspec':d['overspec'],
        'msgs_per_user':round(d['msgs']/len(d['users']),1) if d['users'] else 0,
        'cats':{k:d['cats'].get(k,0) for k in CATN}})

# monthly by group (active users & msgs)
MG=defaultdict(lambda:defaultdict(lambda:{'users':set(),'msgs':0}))
for c in conv:
    g=grp(c['user']); MG[c['month']][g]['users'].add(c['user']); MG[c['month']][g]['msgs']+=c['user_msgs']
monthly_group=[]
for mo in months:
    row={'month':mo}
    for g in ['core','light','user','former']:
        row[g+'_users']=len(MG[mo][g]['users']); row[g+'_msgs']=MG[mo][g]['msgs']
    monthly_group.append(row)

# partners / tools / cats overall
partner=defaultdict(lambda:{'convs':0,'msgs':0,'tier':None,'model':None})
for c in conv:
    p=partner[c['partner'] or 'None']; p['convs']+=1; p['msgs']+=c['user_msgs']+c['asst_msgs']; p['tier']=c['tier']; p['model']=c['model']
partners=sorted([{'partner':k,'model':v['model'],'tier':v['tier'],'convs':v['convs'],'msgs':v['msgs']} for k,v in partner.items()],key=lambda x:-x['msgs'])
toolc=Counter()
for c in conv:
    for t in set(c['tools']): toolc[t]+=1
tools=sorted([{'tool':t,'convs':n} for t,n in toolc.items()],key=lambda x:-x['convs'])
catc=Counter(); cattier=defaultdict(Counter)
for c in conv: catc[c['cat']]+=1; cattier[c['cat']][c['tier']]+=1
cats=sorted([{'code':k,'name':CATN[k],'convs':catc[k],'economy':cattier[k].get('Economy',0),'standard':cattier[k].get('Standard',0),'premium':cattier[k].get('Premium',0)} for k in CATN],key=lambda x:-x['convs'])

# ---- 月次推移: 用途(会話数) / チャットパートナー(メッセージ数) / ツール(利用会話数) ----
# ダッシュボード④のスタック棒グラフ用。系列が多すぎないよう上位N＋「その他」に集約。
TOP_PARTNERS=8; TOP_TOOLS=10
model_total=Counter()
for c in conv: model_total[c['model'] or 'None']+=c['user_msgs']+c['asst_msgs']
top_models=[m for m,_ in model_total.most_common() if m and m!='None'][:TOP_PARTNERS]
top_tools=[t['tool'] for t in tools][:TOP_TOOLS]
MPm=defaultdict(Counter)  # month -> model -> メッセージ数
MTm=defaultdict(Counter)  # month -> tool  -> 利用会話数
for c in conv:
    MPm[c['month']][c['model'] or 'None']+=c['user_msgs']+c['asst_msgs']
    for t in set(c['tools']): MTm[c['month']][t]+=1
# 用途は total 会話数の多い順（cats の並び）で全12カテゴリを系列化
cat_codes=[c['code'] for c in cats]
usage_trend={'labels':[CATN[k] for k in cat_codes],'codes':cat_codes,'months':months,
    'data':[[M[mo]['cats'].get(code,0) for code in cat_codes] for mo in months]}
partner_trend={'labels':top_models,'months':months,
    'data':[[MPm[mo].get(m,0) for m in top_models] for mo in months],
    'other':[sum(v for k,v in MPm[mo].items() if k not in top_models and k!='None') for mo in months]}
tool_trend={'labels':top_tools,'months':months,
    'data':[[MTm[mo].get(t,0) for t in top_tools] for mo in months],
    'other':[sum(v for k,v in MTm[mo].items() if k not in top_tools) for mo in months]}

# quadrants summary + group x quadrant
QN={'Q1':'高頻度・高リテラシー','Q2':'高頻度・低リテラシー','Q3':'低頻度・高リテラシー','Q4':'低頻度・低リテラシー'}
quad=defaultdict(lambda:{'users':0,'convs':0,'msgs':0,'lit':[],'adv':[],'overspec':0})
for r in rows:
    q=quad[r['quadrant']]; q['users']+=1; q['convs']+=r['convs']; q['msgs']+=r['umsgs']
    q['lit'].append(r['literacy']); q['adv'].append(r['adv_rate']); q['overspec']+=r['overspec']
quads=[{'q':q,'name':QN[q],'users':quad[q]['users'],'convs':quad[q]['convs'],'msgs':quad[q]['msgs'],
    'avg_lit':round(statistics.mean(quad[q]['lit']),1) if quad[q]['lit'] else 0,
    'avg_adv':round(statistics.mean(quad[q]['adv'])*100,1) if quad[q]['adv'] else 0,
    'overspec':quad[q]['overspec']} for q in ['Q1','Q2','Q3','Q4']]
gq=defaultdict(Counter)
for r in rows: gq[r['group']][r['quadrant']]+=1
groupquad=[{'group':g,'label':GL[g],
    'Q1':gq[g].get('Q1',0),'Q2':gq[g].get('Q2',0),'Q3':gq[g].get('Q3',0),'Q4':gq[g].get('Q4',0),
    'total':sum(gq[g].values())} for g in ['core','light','user','former'] if g in gq]

# overspec list (exclude claude)
overspec=[]
for c in conv:
    if c['tier'] in ('Standard','Premium') and not claude(c['user']) and c['cat'] in SIMPLE and c['user_msgs']<=2 and not any(t in ADV for t in c['tools']):
        overspec.append({'user':c['user'],'month':c['month'],'model':c['model'],'tier':c['tier'],'cat':CATN[c['cat']],'q':(c['first_user_msg'] or '')[:80]})

# claude users summary
claude_users=[{'user':r['user'],'name':r['name'],'group':r['group'],'convs':r['convs'],'umsgs':r['umsgs'],
    'literacy':r['literacy'],'quadrant':r['quadrant'],'sp_share':round(r['sp_share']*100)} for r in rows if r['claude']]

agg={'months':months,'monthly':monthly,'monthly_group':monthly_group,'partners':partners,'tools':tools,
     'cats':cats,'usage_trend':usage_trend,'partner_trend':partner_trend,'tool_trend':tool_trend,
     'quads':quads,'groupquad':groupquad,'overspec_count':len(overspec),'overspec':overspec[:400],
     'claude_users':claude_users,
     'totals':{'convs':len(conv),'users':len(rows),'msgs':sum(c['user_msgs']+c['asst_msgs'] for c in conv),
        'umsgs':sum(c['user_msgs'] for c in conv),'months':len(months),
        'members':len(members),'active_members':sum(1 for m in members.values() if m['active']),
        'eco':sum(c['user_msgs'] for c in conv if c['tier']=='Economy'),
        'std':sum(c['user_msgs'] for c in conv if c['tier']=='Standard'),
        'pre':sum(c['user_msgs'] for c in conv if c['tier']=='Premium')}}
json.dump(agg, open('aggregates_all.json','w',encoding='utf-8'), ensure_ascii=False)
print('months:',len(months),months[0],'..',months[-1])
print('overspec (excl claude):',len(overspec))
print('groupquad:')
for g in groupquad: print('  ',g['label'],'Q1',g['Q1'],'Q2',g['Q2'],'Q3',g['Q3'],'Q4',g['Q4'],'計',g['total'])
print('claude users:',[(u['user'].split('@')[0],u['quadrant'],u['convs']) for u in claude_users])
print('sample monthly:',monthly[0]['month'],monthly[0]['active_users'],monthly[0]['convs'],'|',monthly[-1]['month'],monthly[-1]['active_users'],monthly[-1]['convs'])
print('trend series - usage:',len(usage_trend['labels']),'cats / partner:',len(top_models),'models / tool:',len(top_tools),'tools (+other)')
print('saved aggregates_all.json')
