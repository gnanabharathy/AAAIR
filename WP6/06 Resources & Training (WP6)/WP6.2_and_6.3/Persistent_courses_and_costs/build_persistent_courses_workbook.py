import sys
import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

SRC = sys.argv[1]
OUT = sys.argv[2]

df = pd.read_excel(SRC, sheet_name='coursework_resources')
tools = pd.read_excel(SRC, sheet_name='course_tools')
sel = df[df.select_reject == 'select'].copy()


def platform(link, provider):
    l = str(link).lower()
    for k, v in [('coursera', 'Coursera'), ('datacamp', 'DataCamp'), ('edx.org', 'edX'),
                 ('udemy', 'Udemy'), ('futurelearn', 'FutureLearn'), ('linkedin', 'LinkedIn Learning'),
                 ('udacity', 'Udacity'), ('kaggle', 'Kaggle'), ('deeplearning.ai', 'DeepLearning.AI'),
                 ('learn.microsoft', 'Microsoft Learn'), ('pluralsight', 'Pluralsight'),
                 ('codecademy', 'Codecademy'), ('365datascience', '365 Data Science'),
                 ('sas.com', 'SAS'), ('mavenanalytics', 'Maven Analytics')]:
        if k in l:
            return v
    return 'Provider own site'


sel['platform'] = [platform(l, p) for l, p in zip(sel.link, sel.provider)]
sel['is_australian'] = sel.country.astype(str).str.contains('Austral')
sel['always_available'] = ((sel.enrolment_status == 'Open enrolment') & (sel.learning_pace == 'Self-paced')
                           & (sel.no_longer_maintained != 'Yes'))

keep = sel.always_available | sel.is_australian | sel.platform.isin(['Coursera', 'DataCamp', 'edX'])
c = sel[keep].copy()


def why(r):
    w = []
    if r.always_available: w.append('Always available')
    if r.is_australian: w.append('Australian')
    if r.platform in ('Coursera', 'DataCamp', 'edX'): w.append(r.platform)
    return '; '.join(w)


c['included_because'] = c.apply(why, axis=1)

# Platform per-seat pricing (USD). Individual figures are from the WP6.2 database access_notes
# (checked June 2026) unless stated. Team figures are from web sources found 10 Nov 2026.
P = [
 # platform, individual seat, individual basis, team seat/yr, team notes, sources, status
 ('Coursera', 399, 'Coursera Plus, per year (list); about $49-59/month monthly',
  399, 'Coursera for Teams, per user per year, 5+ seats (third-party); AUD 566 per user per year reported for Australia (9 Sep 2026)',
  'WP6.2 database access_notes (2026-06-25); coursera.org/courseraplus promo page; trainingcost.com/coursera-for-business-pricing; edubracket.com comparison (read 19 Oct 2026)',
  'Indicative: third-party, not confirmed with vendor'),
 ('DataCamp', 168, 'Premium, per year ($14/month billed annually); one tracker reports a rise to $28/month (about $336/year) from Aug 2026',
  330, 'Teams $27.50 per user per month billed annually, 2-35 seats (DataCamp blog); edubracket lists $14 per user per month ($168/year)',
  'datacamp.com/blog/datacamp-for-business-vs-coursera-for-business; edubracket.com comparison; pricingsaas.com/companies/datacamp/diffs/2026W33',
  'Conflicting sources: confirm with vendor'),
 ('edX', None, 'Priced per course (verified certificate track); see course row',
  None, 'edX for Business Essentials $12.50 per user and Teams $33 per user (billing period not stated); Enterprise by quote',
  'business.edx.org/business/edx-courses-plans (search snippet)',
  'Billing period unconfirmed: confirm with vendor'),
 ('Udemy', None, 'Priced per course, one-off; see course row',
  360, 'Udemy Business Team, per user per year, 2-50 users',
  'edubracket.com comparison; marcandrews.com Udemy Business review 2026; vendr.com/marketplace/udemy',
  'Indicative: third-party'),
 ('LinkedIn Learning', 239.88, 'Per year ($19.99/month billed annually); $39.99/month monthly',
  379.88, 'LinkedIn Learning for Teams, per licence per year, 2-20 users',
  'WP6.2 database access_notes (2026-06-25); trainingcost.com/lms-pricing/linkedin-learning; edubracket.com comparison',
  'Individual: from course page; Team: third-party'),
 ('Udacity', 846, 'All Access 4-month bundle $846 (figure used); or $249/month. NOTE: this column is per 4 months, not per year',
  None, 'No team price found', 'WP6.2 database access_notes (support.udacity.com, 2026-06-26)', 'From course page, June 2026'),
 ('FutureLearn', None, 'ExpertTrack $39/month where subscription applies; many courses free to audit',
  None, 'No team price found', 'WP6.2 database access_notes (2026-06-26)', 'From course page, June 2026'),
 ('DeepLearning.AI', 399, 'Certificates via Coursera Plus or per-specialisation subscription (~$49-59/month)',
  399, 'Via Coursera for Teams', 'WP6.2 database access_notes (2026-06-25)', 'From course page, June 2026'),
 ('Pluralsight', 299.04, 'Standard $24.92/month billed annually; $29/month monthly',
  None, 'No team price found', 'WP6.2 database access_notes (2026-06-25)', 'From course page, June 2026'),
 ('Codecademy', 239.88, 'Pro $19.99/month billed annually; $39.99/month monthly',
  None, 'No team price found', 'WP6.2 database access_notes (codecademy.com/pricing, 2026-06-25)', 'From course page, June 2026'),
 ('365 Data Science', 348, 'Self-Study $29/month billed annually; $36/month monthly',
  None, 'No team price found', 'WP6.2 database access_notes (365datascience.com/pricing, 2026-06-25)', 'From course page, June 2026'),
 ('SAS', None, 'SAS Learning Subscription (annual); price not stated', None, 'Not stated',
  'WP6.2 database access_notes (2026-06-25)', 'Price not available'),
 ('Maven Analytics', None, 'Platform subscription; price not stated', None, 'Not stated',
  'WP6.2 database access_notes (2026-06-25)', 'Price not available'),
 ('Kaggle', 0, 'Free', 0, 'Free', 'WP6.2 database', 'Free'),
 ('Microsoft Learn', 0, 'Free', 0, 'Free', 'WP6.2 database', 'Free'),
]
pricing = pd.DataFrame(P, columns=['platform', 'individual_seat_USD_per_year', 'individual_pricing_basis',
                                   'team_seat_USD_per_year', 'team_pricing_basis', 'sources', 'verification_status'])
pmap = pricing.set_index('platform')


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def seat_cost(r):
    cm = r.cost_model
    lo, cert = num(r.price_lowest_USD), num(r.price_certificate_USD)
    pinfo = pmap.loc[r.platform] if r.platform in pmap.index else None
    if cm == 'Free':
        return 0, 'Free', None
    if cm == 'Free to audit':
        if cert is not None:
            return cert, 'Free to audit; one-off certificate fee shown', None
        if pinfo is not None and pd.notna(pinfo.individual_seat_USD_per_year):
            return pinfo.individual_seat_USD_per_year, 'Free to audit; certificate via platform subscription (per year)', pinfo.team_seat_USD_per_year
        return 0, 'Free to audit; certificate price not stated', None
    if cm == 'Paid':
        return lo, 'One-off course fee' if lo is not None else 'Paid; price not stated', None
    if cm in ('Subscription', 'Freemium'):
        if pinfo is not None:
            return (pinfo.individual_seat_USD_per_year if pd.notna(pinfo.individual_seat_USD_per_year) else None,
                    ('Udacity All Access, 4-month bundle' if r.platform == 'Udacity'
                     else 'Platform subscription per year (covers all platform courses)'),
                    pinfo.team_seat_USD_per_year if pd.notna(pinfo.team_seat_USD_per_year) else None)
        return lo, 'Subscription; platform price not in pricing sheet', None
    if cm == 'Institutional access':
        return None, 'Institutional licence; contact provider', None
    return lo, 'Cost model not stated', None


res = c.apply(seat_cost, axis=1, result_type='expand')
c['indicative_cost_per_seat_USD'] = res[0]
c['cost_per_seat_basis'] = res[1]
c['team_seat_USD_per_year'] = res[2]

cols = ['included_because', 'course_name', 'provider', 'platform', 'country', 'always_available',
        'enrolment_status', 'learning_pace', 'level', 'format', 'duration', 'cost_model',
        'indicative_cost_per_seat_USD', 'cost_per_seat_basis', 'team_seat_USD_per_year',
        'price_lowest_USD', 'price_certificate_USD', 'access_notes', 'primary_tools',
        'health_domain_relevance', 'link', 'course_id']
c = c.sort_values(['platform', 'provider', 'course_name'])

# Priority tools
PRI = ['Electronic Health Records (EHR) analytics', 'R', 'Causal Analysis', 'Regression',
       'SQL & Database management', 'Clinical trial design and analysis', 'GitHub',
       'Clustering & Pattern Recognition', 'NLP Models (BERT, bioBERT, etc.)',
       'Model Interpretability & Explainability', 'Community Engagement Methods']
names = tools.learning_need_tool.dropna().unique()


def match(p):
    if p in names: return [p]
    return [n for n in names if n.lower().startswith(p.lower()[:20])]


rows = []
summary = []
for p in PRI:
    ms = match(p)
    ids = tools[tools.learning_need_tool.isin(ms)].course_id.unique()
    sub = c[c.course_id.isin(ids)].copy()
    sub.insert(0, 'priority_tool', p)
    rows.append(sub)
    costs = sub.indicative_cost_per_seat_USD
    summary.append(dict(priority_tool=p, courses=len(sub), always_available=int(sub.always_available.sum()),
                        australian=int(sub.country.astype(str).str.contains('Austral').sum()),
                        coursera=int((sub.platform == 'Coursera').sum()), datacamp=int((sub.platform == 'DataCamp').sum()),
                        edx=int((sub.platform == 'edX').sum()), free=int((sub.cost_model == 'Free').sum()),
                        median_cost_per_seat_USD=costs.median() if costs.notna().any() else None,
                        min_cost_per_seat_USD=costs.min() if costs.notna().any() else None,
                        max_cost_per_seat_USD=costs.max() if costs.notna().any() else None,
                        cost_not_available=int(costs.isna().sum())))
pri = pd.concat(rows)[['priority_tool'] + cols]
pri_sum = pd.DataFrame(summary)

plat_sum = c.groupby('platform').agg(courses=('course_id', 'count'),
                                     always_available=('always_available', 'sum'),
                                     free=('cost_model', lambda x: (x == 'Free').sum()),
                                     free_to_audit=('cost_model', lambda x: (x == 'Free to audit').sum()),
                                     paid=('cost_model', lambda x: (x == 'Paid').sum()),
                                     subscription=('cost_model', lambda x: (x == 'Subscription').sum()),
                                     institutional=('cost_model', lambda x: (x == 'Institutional access').sum())
                                     ).sort_values('courses', ascending=False).reset_index()

readme = pd.DataFrame({'About this workbook': [
    'Source: AAAIR repository, WP6/06 Resources & Training (WP6)/WP6.2_and_6.3/WP6.2_database_1_30.06.26.xlsx (selected courses only).',
    f'Courses included: {len(c)}. A course is included if it is always available, Australian, or on Coursera, DataCamp or edX.',
    'Always available = enrolment status "Open enrolment", learning pace "Self-paced", and not flagged as no longer maintained.',
    'Australian courses are included whatever their enrolment status, so some are scheduled cohorts or one-off events.',
    'Cost per seat is the indicative cost for one learner in USD. Free = 0. Paid = one-off course fee. Free to audit = certificate fee or platform subscription. Subscription = one year of the platform subscription, which covers every course on that platform.',
    'Team seat price is the published per-user annual price for a team or business plan, where one was found.',
    'Course prices come from the database (checked on course pages, June 2026). Team prices come from web sources found on 10 Nov 2026, mostly third-party. See the Platform pricing sheet for sources and verification status.',
    'All prices are indicative and exclude GST. Confirm with the vendor and ARDC procurement before using them in a budget.',
    'Community Engagement Methods has no matching tool in the course-to-tool mapping, so it has no courses.',
]})

with pd.ExcelWriter(OUT) as w:
    readme.to_excel(w, sheet_name='Read me', index=False)
    pricing.to_excel(w, sheet_name='Platform pricing per seat', index=False)
    pri_sum.to_excel(w, sheet_name='Priority tools summary', index=False)
    pri.to_excel(w, sheet_name='Priority tool courses', index=False)
    c[cols].to_excel(w, sheet_name='All included courses', index=False)
    plat_sum.to_excel(w, sheet_name='By platform', index=False)
    c[c.is_australian][cols].to_excel(w, sheet_name='Australian', index=False)
    for pl in ['Coursera', 'DataCamp', 'edX']:
        c[c.platform == pl][cols].to_excel(w, sheet_name=pl, index=False)

wb = load_workbook(OUT)
for ws in wb.worksheets:
    for cell in ws[1]:
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = PatternFill('solid', fgColor='1F4E78')
        cell.alignment = Alignment(wrap_text=True, vertical='top')
    ws.freeze_panes = 'A2'
    if ws.max_row > 1:
        ws.auto_filter.ref = ws.dimensions
    for i, col in enumerate(ws.iter_cols(min_row=1, max_row=min(ws.max_row, 60)), 1):
        width = max(len(str(x.value)) if x.value is not None else 0 for x in col)
        ws.column_dimensions[get_column_letter(i)].width = min(max(10, width + 2), 60)
    hdr = [x.value for x in ws[1]]
    if 'link' in hdr:
        j = hdr.index('link') + 1
        for r in range(2, ws.max_row + 1):
            cell = ws.cell(r, j)
            if cell.value and str(cell.value).startswith('http'):
                cell.hyperlink = str(cell.value)
                cell.font = Font(color='0563C1', underline='single')
wb['Read me'].column_dimensions['A'].width = 140
wb.save(OUT)

print(len(c)); print(plat_sum.to_string()); print(pri_sum.to_string())
