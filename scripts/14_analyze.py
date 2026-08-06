"""STEP 14: 月次×ユーザー指標・リテラシー・4象限（稼働月正規化） → data/user_all.json, data/meta_all.json"""
import os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import DATA, OUTPUT, norm_key, TEMPLATE_MIN_USERS
os.chdir(DATA)   # 相対パスの read/write は data/ に解決

import json, re, bisect, math, statistics
from collections import defaultdict, Counter

conv=json.load(open('conversations_all.json',encoding='utf-8'))
cls=json.load(open('classification_all.json',encoding='utf-8'))
members=json.load(open('members.json',encoding='utf-8'))

# ---- テンプレ/エージェント由来の初回発話を検出（水増し補正）----
# 同一の正規化初回発話を TEMPLATE_MIN_USERS 人以上が共有 → 定型文とみなす。
# その発話の「文字数」「構造化」は本人の作文力ではないため、加点対象から除外する。
_fu_users=defaultdict(set)
for c in conv:
    if c.get('first_user_msg'):
        _fu_users[norm_key(c['first_user_msg'])].add(c['user'])
TEMPLATE_KEYS={k for k,us in _fu_users.items() if k and len(us)>=TEMPLATE_MIN_USERS}
def is_template(msg):
    return bool(msg) and norm_key(msg) in TEMPLATE_KEYS

CATN={'C01':'メール作成・返信・添削','C02':'文章校正・言い換え・敬語','C03':'資料・企画書・スライド作成',
'C04':'報告書・議事録作成','C05':'営業戦略・企業リサーチ・ABM分析','C06':'製品・素材・技術の相談',
'C07':'画像生成・画像編集','C08':'要約・翻訳・文書処理','C09':'データ・Excel・表・計算',
'C10':'IT・ツール操作サポート','C11':'アイデア出し・ネーミング・コピー','C12':'業務知識・一般調査・その他'}
ADV={'Deep Research (詳細)','文書検索 (RAG)','スライド作成 (PowerPoint)','ファイル出力 (Word、Excelなど)',
'ウェブリサーチ (高速)','国内記事検索','官公需案件検索','音声書き起こし','画像生成 (高性能, GPT-image)',
'画像生成 (高速, Nano Banana)','SharePointファイル検索','Teams検索','Outlookカレンダー予定確認','Box検索','ヘルプページ検索'}
SIMPLE={'C01','C02','C11','C12'}
GRP_LABEL={'core':'コアユーザー','light':'ライトユーザー','user':'ユーザー','none':'未分類','former':'退職/不明'}

def is_structured(m):
    if not m: return False
    if re.search(r'あなたは.{0,25}(専門家|プロ|コピーライター|リサーチャー|コンサル|担当)',m): return True
    if re.search(r'(^|\n)\s*(\d+[\.\)、]|[・\-*#【])',m): return True
    if re.search(r'(条件|前提|背景|目的|制約|フォーマット|以下の|＃|#)',m) and len(m)>120: return True
    return False

for c in conv:
    c['cat']=cls.get(c['conv_id'],'C12')

# member lookup with fallback
def minfo(email):
    m=members.get(email)
    if m: return m
    return {'email':email,'name':'','active':False,'group':'former','created_at':'','last_login':'','claude':False}

# ---- per user aggregation ----
U=defaultdict(lambda:{'convs':0,'umsgs':0,'amsgs':0,'turns':[],'lens':[],'tools':Counter(),
    'toolconvs':0,'advconvs':0,'cats':Counter(),'struct':0,'tiers':Counter(),
    'months':Counter(),'stdprem':0,'overspec':0,'partners':Counter(),
    'rework':0,'tmpl_convs':0,
    'mon_msgs':defaultdict(int),'mon_convs':defaultdict(int),'mon_tier':defaultdict(Counter),
    'mon_adv':defaultdict(int),'mon_cats':defaultdict(Counter)})
for c in conv:
    u=U[c['user']]; mo=c['month']
    tmpl=is_template(c['first_user_msg'])
    # 会話の深さ: 手戻り/やり直し発話を差引いた「実質往復」（最低1）
    adj_turns=max(1, c['user_msgs']-c.get('rework_msgs',0))
    u['convs']+=1; u['umsgs']+=c['user_msgs']; u['amsgs']+=c['asst_msgs']
    u['rework']+=c.get('rework_msgs',0)
    u['turns'].append(adj_turns)
    # 具体性(文字数): テンプレ由来の初回発話は本人の作文でないため集計から除外
    if not tmpl:
        u['lens'].append(c['first_len'])
    else:
        u['tmpl_convs']+=1
    u['cats'][c['cat']]+=1; u['tiers'][c['tier']]+=c['user_msgs']; u['months'][mo]+=1
    u['partners'][c['model']]+=1
    # 構造化: テンプレ由来の構造は本人のリテラシーではないため加点しない（分母は全会話）
    if is_structured(c['first_user_msg']) and not tmpl: u['struct']+=1
    adv=any(t in ADV for t in c['tools'])
    if c['tools']:
        u['toolconvs']+=1
        for t in c['tools']: u['tools'][t]+=1
        if adv: u['advconvs']+=1
    u['mon_msgs'][mo]+=c['user_msgs']; u['mon_convs'][mo]+=1
    u['mon_tier'][mo][c['tier']]+=c['user_msgs']
    if adv: u['mon_adv'][mo]+=1
    u['mon_cats'][mo][c['cat']]+=1
    if c['tier'] in ('Standard','Premium'):
        u['stdprem']+=1
        cl=minfo(c['user'])['claude']
        if (not cl) and c['cat'] in SIMPLE and c['user_msgs']<=2 and not adv:
            u['overspec']+=1

# ---- build user rows ----
rows=[]
for email,u in U.items():
    mi=minfo(email)
    active_months=len(u['months'])
    rows.append({'user':email,'name':mi['name'],'group':mi['group'],'active':mi['active'],
        'claude':mi['claude'],'created_at':mi['created_at'],
        'convs':u['convs'],'umsgs':u['umsgs'],'active_months':active_months,
        'msgs_per_month': u['umsgs']/active_months if active_months else 0,
        'convs_per_month': u['convs']/active_months if active_months else 0,
        'avg_turns':statistics.mean(u['turns']) if u['turns'] else 0,
        'avg_len':statistics.mean(u['lens']) if u['lens'] else 0,
        'adv_rate':u['advconvs']/u['convs'] if u['convs'] else 0,
        'cat_div':len([k for k in u['cats']]),
        'struct_rate':u['struct']/u['convs'] if u['convs'] else 0,
        'distinct_tools':len(u['tools']),
        'rework_rate':u['rework']/u['umsgs'] if u['umsgs'] else 0,
        'tmpl_rate':u['tmpl_convs']/u['convs'] if u['convs'] else 0,
        'stdprem':u['stdprem'],'overspec':u['overspec'],
        'tiers':dict(u['tiers']),'cats':dict(u['cats']),
        'first_month':min(u['months']) if u['months'] else '',
        'last_month':max(u['months']) if u['months'] else '',
        'mon_msgs':dict(u['mon_msgs']),'mon_convs':dict(u['mon_convs'])})

# ---- literacy: percentile of 6 indicators ----
def pr(vals):
    s=sorted(vals); n=len(s)
    return [bisect.bisect_right(s,v)/n*100 for v in vals]
for key in ['avg_turns','avg_len','adv_rate','cat_div','struct_rate','distinct_tools']:
    p=pr([r[key] for r in rows])
    for r,val in zip(rows,p): r['_'+key]=val
W={'_avg_turns':0.18,'_avg_len':0.18,'_adv_rate':0.20,'_cat_div':0.16,'_struct_rate':0.18,'_distinct_tools':0.10}
for r in rows: r['literacy']=round(sum(r[k]*w for k,w in W.items()),1)

# ---- quadrant on fair frequency (msgs per active month) & literacy ----
freq=[r['msgs_per_month'] for r in rows]; lit=[r['literacy'] for r in rows]
mf=statistics.median(freq); ml=statistics.median(lit)
for r in rows:
    hf=r['msgs_per_month']>=mf; hl=r['literacy']>=ml
    r['quadrant']=('Q1' if hf and hl else 'Q2' if hf and not hl else 'Q3' if (not hf) and hl else 'Q4')
    tot=sum(r['tiers'].values()) or 1
    r['sp_share']=(r['tiers'].get('Standard',0)+r['tiers'].get('Premium',0))/tot

tot_rework=sum(c.get('rework_msgs',0) for c in conv); tot_umsg=sum(c['user_msgs'] for c in conv)
tot_tmpl=sum(1 for c in conv if is_template(c.get('first_user_msg')))
print(f'補正: テンプレ定型文キー {len(TEMPLATE_KEYS)}種 / テンプレ由来会話 {tot_tmpl}件({tot_tmpl/len(conv)*100:.1f}%) / '
      f'手戻り発話 {tot_rework}件(全発話の{tot_rework/tot_umsg*100:.1f}%)')
print('users:',len(rows),'median msgs/active-month:',round(mf,1),'median literacy:',ml)
print('quadrants:',dict(Counter(r['quadrant'] for r in rows)))
# correlations
def corr(x,y):
    n=len(x);mx=sum(x)/n;my=sum(y)/n
    c=sum((a-mx)*(b-my) for a,b in zip(x,y));sx=math.sqrt(sum((a-mx)**2 for a in x));sy=math.sqrt(sum((b-my)**2 for b in y))
    return c/(sx*sy) if sx and sy else 0
print('corr freq×lit:',round(corr(freq,lit),3))
print('corr lit×sp_share:',round(corr(lit,[r['sp_share'] for r in rows]),3))
print('corr lit×adv:',round(corr(lit,[r['adv_rate'] for r in rows]),3))

# group x quadrant (usage users with known group only; former separate)
gq=defaultdict(Counter)
for r in rows: gq[r['group']][r['quadrant']]+=1
print('--- group x quadrant ---')
for g in ['core','light','user','former','none']:
    if g in gq: print(' ',GRP_LABEL[g], dict(gq[g]))

json.dump(rows, open('user_all.json','w',encoding='utf-8'), ensure_ascii=False)
json.dump({'median_freq':mf,'median_lit':ml,'cat_names':CATN,'grp_label':GRP_LABEL},
          open('meta_all.json','w',encoding='utf-8'), ensure_ascii=False)
print('saved user_all.json, meta_all.json')
