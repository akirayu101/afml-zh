#!/usr/bin/env python3
from __future__ import annotations

import html
import io
import keyword
import re
import shutil
import subprocess
import token
import tokenize
import unicodedata
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / "afml.pdf"
BOOK = ROOT / "book"
MEDIA = BOOK / "media"
TMP = ROOT / "tmp" / "webbook"
XML = TMP / "afml.xml"
ASSET_CSS = ROOT / "assets" / "afml-book.css"
ASSET_JS = ROOT / "assets" / "afml-book.js"
ASSET_VERSION = "20260706-selection-dialogs"


@dataclass(frozen=True)
class Chapter:
    slug: str
    title: str
    file: str
    start: int
    end: int
    part: str = ""


@dataclass
class Block:
    kind: str
    text: str = ""
    lines: list[str] = field(default_factory=list)
    level: int = 0
    caption: str = ""
    src: str = ""
    section_id: str = ""


CHAPTERS: list[Chapter] = [
    Chapter("front-matter", "Front Matter", "front-matter.html", 1, 29),
    Chapter("chapter-01", "Financial Machine Learning as a Distinct Subject", "chapter-01.html", 30, 49, "Preamble"),
    Chapter("chapter-02", "Financial Data Structures", "chapter-02.html", 50, 69, "Part 1: Data Analysis"),
    Chapter("chapter-03", "Labeling", "chapter-03.html", 70, 85, "Part 1: Data Analysis"),
    Chapter("chapter-04", "Sample Weights", "chapter-04.html", 86, 101, "Part 1: Data Analysis"),
    Chapter("chapter-05", "Fractionally Differentiated Features", "chapter-05.html", 102, 119, "Part 1: Data Analysis"),
    Chapter("chapter-06", "Ensemble Methods", "chapter-06.html", 120, 129, "Part 2: Modelling"),
    Chapter("chapter-07", "Cross-Validation in Finance", "chapter-07.html", 130, 139, "Part 2: Modelling"),
    Chapter("chapter-08", "Feature Importance", "chapter-08.html", 140, 155, "Part 2: Modelling"),
    Chapter("chapter-09", "Hyper-Parameter Tuning with Cross-Validation", "chapter-09.html", 156, 167, "Part 2: Modelling"),
    Chapter("chapter-10", "Bet Sizing", "chapter-10.html", 168, 177, "Part 3: Backtesting"),
    Chapter("chapter-11", "The Dangers of Backtesting", "chapter-11.html", 178, 187, "Part 3: Backtesting"),
    Chapter("chapter-12", "Backtesting through Cross-Validation", "chapter-12.html", 188, 195, "Part 3: Backtesting"),
    Chapter("chapter-13", "Backtesting on Synthetic Data", "chapter-13.html", 196, 221, "Part 3: Backtesting"),
    Chapter("chapter-14", "Backtest Statistics", "chapter-14.html", 222, 237, "Part 3: Backtesting"),
    Chapter("chapter-15", "Understanding Strategy Risk", "chapter-15.html", 238, 247, "Part 3: Backtesting"),
    Chapter("chapter-16", "Machine Learning Asset Allocation", "chapter-16.html", 248, 275, "Part 3: Backtesting"),
    Chapter("chapter-17", "Structural Breaks", "chapter-17.html", 276, 289, "Part 4: Useful Financial Features"),
    Chapter("chapter-18", "Entropy Features", "chapter-18.html", 290, 307, "Part 4: Useful Financial Features"),
    Chapter("chapter-19", "Microstructural Features", "chapter-19.html", 308, 329, "Part 4: Useful Financial Features"),
    Chapter("chapter-20", "Multiprocessing and Vectorization", "chapter-20.html", 330, 345, "Part 5: High-Performance Computing Recipes"),
    Chapter("chapter-21", "Brute Force and Quantum Computers", "chapter-21.html", 346, 355, "Part 5: High-Performance Computing Recipes"),
    Chapter("chapter-22", "High-Performance Computational Intelligence and Forecasting Technologies", "chapter-22.html", 356, 379, "Part 5: High-Performance Computing Recipes"),
    Chapter("index-back", "Index", "book-index.html", 380, 393, "Back Matter"),
]


MATH_CHARS = set("∑∏√≤≥≠≈∞𝜃𝜔𝜎𝜏𝜇𝛽𝛿𝜋ΛΔ{}[]|′̂̃∈∉−±×÷")
SECTION_RE = re.compile(r"^(\d+\.\d+(?:\.\d+)?(?:\.\d+)?)\s+(.+)$")
SNIPPET_RE = re.compile(r"^SNIPPET\s+(\d+\.\d+)\s+(.+)$")
TABLE_RE = re.compile(r"^TABLE\s+(\d+\.\d+)\s+(.+)$")
FIGURE_RE = re.compile(r"^FIGURE\s+(\d+\.\d+)\s+(.+)$")

CHAPTER_02_MATH_OVERRIDES: list[str | None] = [
    r"b_t=\begin{cases} b_{t-1}, & \Delta p_t=0,\\ \dfrac{|\Delta p_t|}{\Delta p_t}, & \Delta p_t\ne 0.\end{cases}",
    "",
    r"\theta_T=\sum_{t=1}^{T} b_t",
    "",
    r"\mathbb{E}_0[\theta_T]=\mathbb{E}_0[T]\bigl(2P[b_t=1]-1\bigr)",
    r"T^*=\arg\min_T\left\{|\theta_T|\ge \mathbb{E}_0[T]\left|2P[b_t=1]-1\right|\right\}",
    r"\theta_T=\sum_{t=1}^{T} b_t v_t",
    "",
    r"\mathbb{E}_0[\theta_T]=\mathbb{E}_0\left[\sum_{t|b_t=1} v_t\right]-\mathbb{E}_0\left[\sum_{t|b_t=-1} v_t\right]=\mathbb{E}_0[T]\left(P[b_t=1]\mathbb{E}_0[v_t|b_t=1]-P[b_t=-1]\mathbb{E}_0[v_t|b_t=-1]\right)",
    "",
    "",
    r"\mathbb{E}_0[T]^{-1}\mathbb{E}_0\left[\sum_{t=1}^{T}v_t\right]=\mathbb{E}_0[v_t]=v^+ + v^-",
    r"\mathbb{E}_0[\theta_T]=\mathbb{E}_0[T](v^+-v^-)=\mathbb{E}_0[T]\left(2v^+-\mathbb{E}_0[v_t]\right)",
    r"T^*=\arg\min_T\left\{|\theta_T|\ge \mathbb{E}_0[T]\left|2v^+-\mathbb{E}_0[v_t]\right|\right\}",
    r"\theta_T=\max\left\{\sum_{t|b_t=1}b_t,\;-\sum_{t|b_t=-1}b_t\right\}",
    "",
    r"\mathbb{E}_0[\theta_T]=\mathbb{E}_0[T]\max\{P[b_t=1],1-P[b_t=1]\}",
    r"T^*=\arg\min_T\left\{\theta_T\ge \mathbb{E}_0[T]\max\{P[b_t=1],1-P[b_t=1]\}\right\}",
    r"\theta_T=\max\left\{\sum_{t|b_t=1}b_t v_t,\;-\sum_{t|b_t=-1}b_t v_t\right\}",
    "",
    r"\mathbb{E}_0[\theta_T]=\mathbb{E}_0[T]\max\{P[b_t=1]\mathbb{E}_0[v_t|b_t=1],(1-P[b_t=1])\mathbb{E}_0[v_t|b_t=-1]\}",
    r"T^*=\arg\min_T\left\{\theta_T\ge \mathbb{E}_0[T]\max\{P[b_t=1]\mathbb{E}_0[v_t|b_t=1],(1-P[b_t=1])\mathbb{E}_0[v_t|b_t=-1]\}\right\}",
    "",
    r"\begin{aligned}h_{i,t}&=\begin{cases}\dfrac{\omega_{i,t}K_t}{o_{i,t+1}\varphi_{i,t}\sum_{i=1}^{I}|\omega_{i,t}|}, & t\in B,\\ h_{i,t-1}, & \text{otherwise},\end{cases}\\[0.35em]\delta_{i,t}&=\begin{cases}p_{i,t}-o_{i,t}, & (t-1)\in B,\\ \Delta p_{i,t}, & \text{otherwise},\end{cases}\\[0.35em]K_t&=K_{t-1}+\sum_{i=1}^{I}h_{i,t-1}\varphi_{i,t}(\delta_{i,t}+d_{i,t}).\end{aligned}",
    "",
    "",
    "",
    "",
    r"\sigma^2=\omega'V\omega=\omega'W\Lambda W'\omega=\beta'\Lambda\beta=(\Lambda^{1/2}\beta)'(\Lambda^{1/2}\beta)",
    r"R_n=\beta_n^2\Lambda_{n,n}\sigma^{-2}=[W'\omega]_n^2\Lambda_{n,n}\sigma^{-2}",
    r"S_t=\max\{0,S_{t-1}+y_t-\mathbb{E}_{t-1}[y_t]\}",
    r"S_t\ge h\Longleftrightarrow \exists \tau\in[1,t]\; \sum_{i=\tau}^{t}\left(y_i-\mathbb{E}_{i-1}[y_i]\right)\ge h",
    r"\begin{aligned}S_t^+&=\max\{0,S_{t-1}^+ + y_t-\mathbb{E}_{t-1}[y_t]\},\quad S_0^+=0,\\S_t^-&=\min\{0,S_{t-1}^- + y_t-\mathbb{E}_{t-1}[y_t]\},\quad S_0^-=0,\\S_t&=\max\{S_t^+,-S_t^-\}.\end{aligned}",
    r"\mathbb{E}_{t-1}[y_t]=y_{t-1}.",
]

CHAPTER_03_MATH_OVERRIDES: list[str | None] = [
    "",
    r"y_i=\begin{cases}-1, & r_{t_{i,0},t_{i,0}+h}<-\tau,\\0, & |r_{t_{i,0},t_{i,0}+h}|\le\tau,\\1, & r_{t_{i,0},t_{i,0}+h}>\tau,\end{cases}",
    "",
    r"r_{t_{i,0},t_{i,0}+h}=\dfrac{p_{t_{i,0}+h}}{p_{t_{i,0}}}-1",
]

CHAPTER_02_CODE_OVERRIDES: dict[str, str] = {
    "Snippet 2.1:": """def pcaWeights(cov, riskDist=None, riskTarget=1.):
    # Following the riskAlloc distribution, match riskTarget
    eVal, eVec = np.linalg.eigh(cov)  # must be Hermitian
    indices = eVal.argsort()[::-1]  # arguments for sorting eVal desc
    eVal, eVec = eVal[indices], eVec[:, indices]
    if riskDist is None:
        riskDist = np.zeros(cov.shape[0])
        riskDist[-1] = 1.
    loads = riskTarget * (riskDist / eVal) ** .5
    wghts = np.dot(eVec, np.reshape(loads, (-1, 1)))
    # ctr = (loads / riskTarget) ** 2 * eVal  # verify riskDist
    return wghts""",
    "Snippet 2.2:": """def getRolledSeries(pathIn, key):
    series = pd.read_hdf(pathIn, key='bars/ES_10k')
    series['Time'] = pd.to_datetime(series['Time'], format='%Y%m%d%H%M%S%f')
    series = series.set_index('Time')
    gaps = rollGaps(series)
    for fld in ['Close', 'VWAP']:
        series[fld] -= gaps
    return series


def rollGaps(
    series,
    dictio={
        'Instrument': 'FUT_CUR_GEN_TICKER',
        'Open': 'PX_OPEN',
        'Close': 'PX_LAST',
    },
    matchEnd=True,
):
    # Compute gaps at each roll, between previous close and next open
    rollDates = series[dictio['Instrument']].drop_duplicates(keep='first').index
    gaps = series[dictio['Close']] * 0
    iloc = list(series.index)
    iloc = [iloc.index(i) - 1 for i in rollDates]  # index of days prior to roll
    gaps.loc[rollDates[1:]] = (
        series[dictio['Open']].loc[rollDates[1:]]
        - series[dictio['Close']].iloc[iloc[1:]].values
    )
    gaps = gaps.cumsum()
    if matchEnd:
        gaps -= gaps.iloc[-1]  # roll backward
    return gaps""",
    "Snippet 2.3:": """raw = pd.read_csv(filePath, index_col=0, parse_dates=True)
gaps = rollGaps(raw, dictio={'Instrument': 'Symbol', 'Open': 'Open', 'Close': 'Close'})
rolled = raw.copy(deep=True)
for fld in ['Open', 'Close']:
    rolled[fld] -= gaps
rolled['Returns'] = rolled['Close'].diff() / raw['Close'].shift(1)
rolled['rPrices'] = (1 + rolled['Returns']).cumprod()""",
    "Snippet 2.4:": """def getTEvents(gRaw, h):
    tEvents, sPos, sNeg = [], 0, 0
    diff = gRaw.diff()
    for i in diff.index[1:]:
        sPos = max(0, sPos + diff.loc[i])
        sNeg = min(0, sNeg + diff.loc[i])
        if sNeg < -h:
            sNeg = 0
            tEvents.append(i)
        elif sPos > h:
            sPos = 0
            tEvents.append(i)
    return pd.DatetimeIndex(tEvents)""",
}

CHAPTER_03_CODE_OVERRIDES: dict[str, str] = {
    "Snippet 3.2:": """def applyPtSlOnT1(close, events, ptSl, molecule):
    # apply stop loss/profit taking, if it takes place before t1 (end of event)
    events_ = events.loc[molecule]
    out = events_[['t1']].copy(deep=True)
    if ptSl[0] > 0:
        pt = ptSl[0] * events_['trgt']
    else:
        pt = pd.Series(index=events.index)  # NaNs
    if ptSl[1] > 0:
        sl = -ptSl[1] * events_['trgt']
    else:
        sl = pd.Series(index=events.index)  # NaNs
    for loc, t1 in events_['t1'].fillna(close.index[-1]).iteritems():
        df0 = close[loc:t1]  # path prices
        df0 = (df0 / close[loc] - 1) * events_.at[loc, 'side']  # path returns
        out.loc[loc, 'sl'] = df0[df0 < sl[loc]].index.min()  # earliest stop loss
        out.loc[loc, 'pt'] = df0[df0 > pt[loc]].index.min()  # earliest profit taking
    return out""",
    "Snippet 3.6:": """def getEvents(close, tEvents, ptSl, trgt, minRet, numThreads, t1=False, side=None):
    # 1) get target
    trgt = trgt.loc[tEvents]
    trgt = trgt[trgt > minRet]  # minRet
    # 2) get t1 (max holding period)
    if t1 is False:
        t1 = pd.Series(pd.NaT, index=tEvents)
    # 3) form events object, apply stop loss on t1
    if side is None:
        side_, ptSl_ = pd.Series(1., index=trgt.index), [ptSl[0], ptSl[0]]
    else:
        side_, ptSl_ = side.loc[trgt.index], ptSl[:2]
    events = pd.concat({'t1': t1, 'trgt': trgt, 'side': side_},
                       axis=1).dropna(subset=['trgt'])
    df0 = mpPandasObj(func=applyPtSlOnT1, pdObj=('molecule', events.index),
                      numThreads=numThreads, close=close, events=events, ptSl=ptSl_)
    events['t1'] = df0.dropna(how='all').min(axis=1)  # pd.min ignores nan
    if side is None:
        events = events.drop('side', axis=1)
    return events""",
    "Snippet 3.8:": """def dropLabels(events, minPct=.05):
    # apply weights, drop labels with insufficient examples
    while True:
        df0 = events['bin'].value_counts(normalize=True)
        if df0.min() > minPct or df0.shape[0] < 3:
            break
        print 'dropped label', df0.argmin(), df0.min()
        events = events[events['bin'] != df0.argmin()]
    return events""",
}

CHAPTER_04_MATH_OVERRIDES: list[str | None] = [""] * 50

CHAPTER_04_CODE_OVERRIDES: dict[str, str] = {
    "Snippet 4.1:": """def mpNumCoEvents(closeIdx, t1, molecule):
    '''
    Compute the number of concurrent events per bar.
    +molecule[0] is the date of the first event on which the weight will be computed
    +molecule[-1] is the date of the last event on which the weight will be computed
    Any event that starts before t1[molecule].max() impacts the count.
    '''
    # 1) find events that span the period [molecule[0], molecule[-1]]
    t1 = t1.fillna(closeIdx[-1])  # unclosed events still must impact other weights
    t1 = t1[t1 >= molecule[0]]  # events that end at or after molecule[0]
    t1 = t1.loc[:t1[molecule].max()]  # events that start at or before t1[molecule].max()
    # 2) count events spanning a bar
    iloc = closeIdx.searchsorted(np.array([t1.index[0], t1.max()]))
    count = pd.Series(0, index=closeIdx[iloc[0]:iloc[1] + 1])
    for tIn, tOut in t1.iteritems():
        count.loc[tIn:tOut] += 1.
    return count.loc[molecule[0]:t1[molecule].max()]""",
    "Snippet 4.9:": """import pandas as pd, numpy as np
from mpEngine import processJobs, processJobs_


def mainMC(numObs=10, numBars=100, maxH=5, numIters=1E6, numThreads=24):
    # Monte Carlo experiments
    jobs = []
    for i in xrange(int(numIters)):
        job = {'func': auxMC, 'numObs': numObs, 'numBars': numBars, 'maxH': maxH}
        jobs.append(job)
    if numThreads == 1:
        out = processJobs_(jobs)
    else:
        out = processJobs(jobs, numThreads=numThreads)
    print pd.DataFrame(out).describe()
        return""",
}

CHAPTER_05_MATH_OVERRIDES: list[str | None] = [""] * 50

CHAPTER_05_CODE_OVERRIDES: dict[str, str] = {
    "Snippet 5.3:": """def fracDiff_FFD(series,d,thres=1e-5):
    '''
    Constant width window (new solution)
    Note 1: thres determines the cut-off weight for the window
    Note 2: d can be any positive fractional, not necessarily bounded [0,1].
    '''
    #1) Compute weights for the longest series
    w=getWeights_FFD(d,thres)
    width=len(w)-1
    #2) Apply weights to values
    df={}
    for name in series.columns:
        seriesF,df_=series[[name]].fillna(method='ffill').dropna(),pd.Series()
        for iloc1 in range(width,seriesF.shape[0]):
            loc0,loc1=seriesF.index[iloc1-width],seriesF.index[iloc1]
            if not np.isfinite(series.loc[loc1,name]):
                continue # exclude NAs
            df_[loc1]=np.dot(w.T,seriesF.loc[loc0:loc1])[0,0]
        df[name]=df_.copy(deep=True)
    df=pd.concat(df,axis=1)
    return df""",
}

CHAPTER_08_CODE_OVERRIDES: dict[str, str] = {
    "Snippet 8.2:": """def featImpMDI(fit,featNames):
    # feat importance based on IS mean impurity reduction
    df0={i:tree.feature_importances_ for i,tree in enumerate(fit.estimators_)}
    df0=pd.DataFrame.from_dict(df0,orient='index')
    df0.columns=featNames
    df0=df0.replace(0,np.nan) # because max_features=1
    imp=pd.concat({'mean':df0.mean(),'std':df0.std()*df0.shape[0]**-.5},axis=1)
    imp/=imp['mean'].sum()
    return imp""",
    "Snippet 8.3:": """def featImpMDA(clf,X,y,cv,sample_weight,t1,pctEmbargo,scoring='neg_log_loss'):
    # feat importance based on OOS score reduction
    if scoring not in ['neg_log_loss','accuracy']:
        raise Exception('wrong scoring method.')
    from sklearn.metrics import log_loss,accuracy_score
    cvGen=PurgedKFold(n_splits=cv,t1=t1,pctEmbargo=pctEmbargo) # purged cv
    scr0,scr1=pd.Series(),pd.DataFrame(columns=X.columns)
    for i,(train,test) in enumerate(cvGen.split(X=X)):
        X0,y0,w0=X.iloc[train,:],y.iloc[train],sample_weight.iloc[train]
        X1,y1,w1=X.iloc[test,:],y.iloc[test],sample_weight.iloc[test]
        fit=clf.fit(X=X0,y=y0,sample_weight=w0.values)
        if scoring=='neg_log_loss':
            prob=fit.predict_proba(X1)
            scr0.loc[i]=-log_loss(y1,prob,sample_weight=w1.values,
                                  labels=clf.classes_)
        else:
            pred=fit.predict(X1)
            scr0.loc[i]=accuracy_score(y1,pred,sample_weight=w1.values)
        for j in X.columns:
            X1_=X1.copy(deep=True)
            np.random.shuffle(X1_[j].values) # permutation of a single column
            if scoring=='neg_log_loss':
                prob=fit.predict_proba(X1_)
                scr1.loc[i,j]=-log_loss(y1,prob,sample_weight=w1.values,
                                        labels=clf.classes_)
            else:
                pred=fit.predict(X1_)
                scr1.loc[i,j]=accuracy_score(y1,pred,sample_weight=w1.values)
    imp=(-scr1).add(scr0,axis=0)
    if scoring=='neg_log_loss':
        imp=imp/-scr1
    else:
        imp=imp/(1.-scr1)
    imp=pd.concat({'mean':imp.mean(),'std':imp.std()*imp.shape[0]**-.5},axis=1)
    return imp,scr0.mean()""",
    "Snippet 8.7:": """def getTestData(n_features=40,n_informative=10,n_redundant=10,n_samples=10000):
    # generate a random dataset for a classification problem
    from sklearn.datasets import make_classification
    trnsX,cont=make_classification(n_samples=n_samples,n_features=n_features,
        n_informative=n_informative,n_redundant=n_redundant,random_state=0,
        shuffle=False)
    df0=pd.DatetimeIndex(periods=n_samples,freq=pd.tseries.offsets.BDay(),
                         end=pd.datetime.today())
    trnsX=pd.DataFrame(trnsX,index=df0)
    cont=pd.Series(cont,index=df0).to_frame('bin')
    df0=['I_'+str(i) for i in xrange(n_informative)]+[
        'R_'+str(i) for i in xrange(n_redundant)]
    df0+=['N_'+str(i) for i in xrange(n_features-len(df0))]
    trnsX.columns=df0
    cont['w']=1./cont.shape[0]
    cont['t1']=pd.Series(cont.index,index=cont.index)
    return trnsX,cont""",
    "Snippet 8.8:": """def featImportance(trnsX,cont,n_estimators=1000,cv=10,max_samples=1.,numThreads=24,
                   pctEmbargo=0,scoring='accuracy',method='SFI',minWLeaf=0.,**kargs):
    # feature importance from a random forest
    from sklearn.tree import DecisionTreeClassifier
    from sklearn.ensemble import BaggingClassifier
    from mpEngine import mpPandasObj
    n_jobs=(-1 if numThreads>1 else 1) # run 1 thread with ht_helper in dirac1
    # 1) prepare classifier, cv. max_features=1, to prevent masking
    clf=DecisionTreeClassifier(criterion='entropy',max_features=1,
        class_weight='balanced',min_weight_fraction_leaf=minWLeaf)
    clf=BaggingClassifier(base_estimator=clf,n_estimators=n_estimators,
        max_features=1.,max_samples=max_samples,oob_score=True,n_jobs=n_jobs)
    fit=clf.fit(X=trnsX,y=cont['bin'],sample_weight=cont['w'].values)
    oob=fit.oob_score_
    if method=='MDI':
        imp=featImpMDI(fit,featNames=trnsX.columns)
        oos=cvScore(clf,X=trnsX,y=cont['bin'],cv=cv,sample_weight=cont['w'],
                    t1=cont['t1'],pctEmbargo=pctEmbargo,scoring=scoring).mean()
    elif method=='MDA':
        imp,oos=featImpMDA(clf,X=trnsX,y=cont['bin'],cv=cv,sample_weight=cont['w'],
                           t1=cont['t1'],pctEmbargo=pctEmbargo,scoring=scoring)
    elif method=='SFI':
        cvGen=PurgedKFold(n_splits=cv,t1=cont['t1'],pctEmbargo=pctEmbargo)
        oos=cvScore(clf,X=trnsX,y=cont['bin'],sample_weight=cont['w'],
                    scoring=scoring,cvGen=cvGen).mean()
        clf.n_jobs=1 # parallelize auxFeatImpSFI rather than clf
        imp=mpPandasObj(auxFeatImpSFI,('featNames',trnsX.columns),numThreads,
                        clf=clf,trnsX=trnsX,cont=cont,scoring=scoring,cvGen=cvGen)
    return imp,oob,oos""",
    "Snippet 8.9:": """def testFunc(n_features=40,n_informative=10,n_redundant=10,n_estimators=1000,
             n_samples=10000,cv=10):
    # test the performance of the feat importance functions on artificial data
    # Nr noise features = n_features-n_informative-n_redundant
    trnsX,cont=getTestData(n_features,n_informative,n_redundant,n_samples)
    dict0={'minWLeaf':[0.],'scoring':['accuracy'],'method':['MDI','MDA','SFI'],
           'max_samples':[1.]}
    jobs,out=(dict(izip(dict0,i)) for i in product(*dict0.values())),[]
    kargs={'pathOut':'./testFunc/','n_estimators':n_estimators,
           'tag':'testFunc','cv':cv}
    for job in jobs:
        job['simNum']=job['method']+'_'+job['scoring']+'_'+'%.2f'%job['minWLeaf']+ \\
                      '_'+str(job['max_samples'])
        print job['simNum']
        kargs.update(job)
        imp,oob,oos=featImportance(trnsX=trnsX,cont=cont,**kargs)
        plotFeatImportance(imp=imp,oob=oob,oos=oos,**kargs)
        df0=imp[['mean']]/imp['mean'].abs().sum()
        df0['type']=[i[0] for i in df0.index]
        df0=df0.groupby('type')['mean'].sum().to_dict()
        df0.update({'oob':oob,'oos':oos})
        df0.update(job)
        out.append(df0)
    out=pd.DataFrame(out).sort_values(['method','scoring','minWLeaf','max_samples'])
    out=out[['method','scoring','minWLeaf','max_samples','I','R','N','oob','oos']]
    out.to_csv(kargs['pathOut']+'stats.csv')
    return""",
}

CHAPTER_09_MATH_OVERRIDES: list[str | None] = [""] * 6

CHAPTER_09_CODE_OVERRIDES: dict[str, str] = {
    "Snippet 9.1:": """def clfHyperFit(feat,lbl,t1,pipe_clf,param_grid,cv=3,bagging=[0,None,1.],
                 n_jobs=-1,pctEmbargo=0,**fit_params):
    if set(lbl.values)=={0,1}:scoring='f1' # f1 for meta-labeling
    else:scoring='neg_log_loss' # symmetric towards all cases
    #1) hyperparameter search, on train data
    inner_cv=PurgedKFold(n_splits=cv,t1=t1,pctEmbargo=pctEmbargo) # purged
    gs=GridSearchCV(estimator=pipe_clf,param_grid=param_grid,
        scoring=scoring,cv=inner_cv,n_jobs=n_jobs,iid=False)
    gs=gs.fit(feat,lbl,**fit_params).best_estimator_ # pipeline
    #2) fit validated model on the entirety of the data
    if bagging[1]>0:
        gs=BaggingClassifier(base_estimator=MyPipeline(gs.steps),
             n_estimators=int(bagging[0]),max_samples=float(bagging[1]),
             max_features=float(bagging[2]),n_jobs=n_jobs)
        gs=gs.fit(feat,lbl,sample_weight=fit_params \\
             [gs.base_estimator.steps[-1][0]+'__sample_weight'])
        gs=Pipeline([('bag',gs)])
    return gs""",
    "Snippet 9.2:": """class MyPipeline(Pipeline):
    def fit(self,X,y,sample_weight=None,**fit_params):
        if sample_weight is not None:
             fit_params[self.steps[-1][0]+'__sample_weight']=sample_weight
        return super(MyPipeline,self).fit(X,y,**fit_params)""",
    "Snippet 9.3:": """def clfHyperFit(feat,lbl,t1,pipe_clf,param_grid,cv=3,bagging=[0,None,1.],
                rndSearchIter=0,n_jobs=-1,pctEmbargo=0,**fit_params):
    if set(lbl.values)=={0,1}:scoring='f1' # f1 for meta-labeling
    else:scoring='neg_log_loss' # symmetric towards all cases
    #1) hyperparameter search, on train data
    inner_cv=PurgedKFold(n_splits=cv,t1=t1,pctEmbargo=pctEmbargo) # purged
    if rndSearchIter==0:
        gs=GridSearchCV(estimator=pipe_clf,param_grid=param_grid,
            scoring=scoring,cv=inner_cv,n_jobs=n_jobs,iid=False)
    else:
        gs=RandomizedSearchCV(estimator=pipe_clf,param_distributions= \\
            param_grid,scoring=scoring,cv=inner_cv,n_jobs=n_jobs,
            iid=False,n_iter=rndSearchIter)
    gs=gs.fit(feat,lbl,**fit_params).best_estimator_ # pipeline
    #2) fit validated model on the entirety of the data
    if bagging[1]>0:
        gs=BaggingClassifier(base_estimator=MyPipeline(gs.steps),
             n_estimators=int(bagging[0]),max_samples=float(bagging[1]),
             max_features=float(bagging[2]),n_jobs=n_jobs)
        gs=gs.fit(feat,lbl,sample_weight=fit_params \\
             [gs.base_estimator.steps[-1][0]+'__sample_weight'])
        gs=Pipeline([('bag',gs)])
    return gs""",
    "Snippet 9.4:": """import numpy as np,pandas as pd,matplotlib.pyplot as mpl
from scipy.stats import rv_continuous,kstest
#---------------------------------------
class logUniform_gen(rv_continuous):
    # random numbers log-uniformly distributed between 1 and e
    def _cdf(self,x):
        return np.log(x/self.a)/np.log(self.b/self.a)
def logUniform(a=1,b=np.exp(1)):return logUniform_gen(a=a,b=b,name='logUniform')
#---------------------------------------
a,b,size=1E-3,1E3,10000
vals=logUniform(a=a,b=b).rvs(size=size)
print kstest(rvs=np.log(vals),cdf='uniform',args=(np.log(a),np.log(b/a)),N=size)
print pd.Series(vals).describe()
mpl.subplot(121)
pd.Series(np.log(vals)).hist()
mpl.subplot(122)
pd.Series(vals).hist()
mpl.show()""",
}

CHAPTER_10_MATH_OVERRIDES: list[str | None] = [""] * 20

CHAPTER_11_MATH_OVERRIDES: list[str | None] = [""] * 12

CHAPTER_12_MATH_OVERRIDES: list[str | None] = [""] * 12

CHAPTER_13_MATH_OVERRIDES: list[str | None] = [""] * 80

CHAPTER_14_MATH_OVERRIDES: list[str | None] = [""] * 40

CHAPTER_10_CODE_OVERRIDES: dict[str, str] = {
    "Snippet 10.1:": """def getSignal(events,stepSize,prob,pred,numClasses,numThreads,**kargs):
    # get signals from predictions
    if prob.shape[0]==0:return pd.Series()
    #1) generate signals from multinomial classification (one-vs-rest, OvR)
    signal0=(prob-1./numClasses)/(prob*(1.-prob))**.5 # t-value of OvR
    signal0=pred*(2*norm.cdf(signal0)-1) # signal=side*size
    if 'side' in events:signal0*=events.loc[signal0.index,'side'] # meta-labeling
    #2) compute average signal among those concurrently open
    df0=signal0.to_frame('signal').join(events[['t1']],how='left')
    df0=avgActiveSignals(df0,numThreads)
    signal1=discreteSignal(signal0=df0,stepSize=stepSize)
    return signal1""",
    "Snippet 10.2:": """def avgActiveSignals(signals,numThreads):
    # compute the average signal among those active
    #1) time points where signals change (either one starts or one ends)
    tPnts=set(signals['t1'].dropna().values)
    tPnts=tPnts.union(signals.index.values)
    tPnts=list(tPnts);tPnts.sort()
    out=mpPandasObj(mpAvgActiveSignals,('molecule',tPnts),numThreads,signals=signals)
    return out
#---------------------------------------
def mpAvgActiveSignals(signals,molecule):
    '''
    At time loc, average signal among those still active.
    Signal is active if:
        a) issued before or at loc AND
        b) loc before signal's endtime, or endtime is still unknown (NaT).
    '''
    out=pd.Series()
    for loc in molecule:
        df0=(signals.index.values<=loc)&((loc<signals['t1'])|pd.isnull(signals['t1']))
        act=signals[df0].index
        if len(act)>0:out[loc]=signals.loc[act,'signal'].mean()
        else:out[loc]=0 # no signals active at this time
    return out""",
    "Snippet 10.3:": """def discreteSignal(signal0,stepSize):
    # discretize signal
    signal1=(signal0/stepSize).round()*stepSize # discretize
    signal1[signal1>1]=1 # cap
    signal1[signal1<-1]=-1 # floor
    return signal1""",
    "Snippet 10.4:": """def betSize(w,x):
    return x*(w+x**2)**-.5
#---------------------------------------
def getTPos(w,f,mP,maxPos):
    return int(betSize(w,f-mP)*maxPos)
#---------------------------------------
def invPrice(f,w,m):
    return f-m*(w/(1-m**2))**.5
#---------------------------------------
def limitPrice(tPos,pos,f,w,maxPos):
    sgn=(1 if tPos>=pos else -1)
    lP=0
    for j in xrange(abs(pos+sgn),abs(tPos+1)):
        lP+=invPrice(f,w,j/float(maxPos))
    lP/=tPos-pos
    return lP
#---------------------------------------
def getW(x,m):
    # 0<alpha<1
    return x**2*(m**-2-1)
#---------------------------------------
def main():
    pos,maxPos,mP,f,wParams=0,100,100,115,{'divergence':10,'m':.95}
    w=getW(wParams['divergence'],wParams['m']) # calibrate w
    tPos=getTPos(w,f,mP,maxPos) # get tPos
    lP=limitPrice(tPos,pos,f,w,maxPos) # limit price for order
    return
#---------------------------------------
if __name__=='__main__':main()""",
}

CHAPTER_13_CODE_OVERRIDES: dict[str, str] = {
    "Snippet 13.2: Python Code for the Determination of Optimal Trading Rules": """def batch(coeffs, nIter=1e5, maxHP=100, rPT=np.linspace(.5, 10, 20),
          rSLm=np.linspace(.5, 10, 20), seed=0):
    phi, output1 = 2 ** (-1. / coeffs['hl']), []
    for comb_ in product(rPT, rSLm):
        output2 = []
        for iter_ in range(int(nIter)):
            p, hp, count = seed, 0, 0
            while True:
                p = ((1 - phi) * coeffs['forecast'] + phi * p
                     + coeffs['sigma'] * gauss(0, 1))
                cP = p - seed
                hp += 1
                if cP > comb_[0] or cP < -comb_[1] or hp > maxHP:
                    output2.append(cP)
                    break
        mean, std = np.mean(output2), np.std(output2)
        print comb_[0], comb_[1], mean, std, mean / std
        output1.append((comb_[0], comb_[1], mean, std, mean / std))
    return output1""",
}

CHAPTER_14_CODE_OVERRIDES: dict[str, str] = {
    "Snippet 14.3: Algorithm for Deriving HHI Concentration": """rHHIPos=getHHI(ret[ret>=0]) # concentration of positive returns per bet
rHHINeg=getHHI(ret[ret<0]) # concentration of negative returns per bet
tHHI=getHHI(ret.groupby(pd.TimeGrouper(freq='M')).count()) # concentr. bets/month
#---------------------------------------
def getHHI(betRet):
    if betRet.shape[0]<=2:return np.nan
    wght=betRet/betRet.sum()
    hhi=(wght**2).sum()
    hhi=(hhi-betRet.shape[0]**-1)/(1.-betRet.shape[0]**-1)
    return hhi""",
}

CHAPTER_06_MATH_OVERRIDES: list[str | None] = [""] * 20

CHAPTER_15_CODE_OVERRIDES: dict[str, str] = {
    "Snippet 15.1:": """out,p=[],.55
for i in xrange(1000000):
    rnd=np.random.binomial(n=1,p=p)
    x=(1 if rnd==1 else -1)
    out.append(x)
print np.mean(out),np.std(out),np.mean(out)/np.std(out)""",
    "Snippet 15.2:": """>>> from sympy import *
>>> init_printing(use_unicode=False,wrap_line=False,no_global=True)
>>> p,u,d=symbols('p u d')
>>> m2=p*u**2+(1-p)*d**2
>>> m1=p*u+(1-p)*d
>>> v=m2-m1**2
>>> factor(v)""",
    "Snippet 15.3:": """def binHR(sl,pt,freq,tSR):
    '''
    Given a trading rule characterized by the parameters {sl,pt,freq},
    what's the min precision p required to achieve a Sharpe ratio tSR?
    1) Inputs
    sl: stop loss threshold
    pt: profit taking threshold
    freq: number of bets per year
    tSR: target annual Sharpe ratio
    2) Output
    p: the min precision rate p required to achieve tSR
    '''
    a=(freq+tSR**2)*(pt-sl)**2
    b=(2*freq*sl-tSR**2*(pt-sl))*(pt-sl)
    c=freq*sl**2
    p=(-b+(b**2-4*a*c)**.5)/(2.*a)
    return p""",
    "Snippet 15.4:": """def binFreq(sl,pt,p,tSR):
    '''
    Given a trading rule characterized by the parameters {sl,pt,freq},
    what's the number of bets/year needed to achieve a Sharpe ratio
    tSR with precision rate p?
    Note: Equation with radicals, check for extraneous solution.
    1) Inputs
    sl: stop loss threshold
    pt: profit taking threshold
    p: precision rate p
    tSR: target annual Sharpe ratio
    2) Output
    freq: number of bets per year needed
    '''
    freq=(tSR*(pt-sl))**2*p*(1-p)/((pt-sl)*p+sl)**2 # possible extraneous
    if not np.isclose(binSR(sl,pt,freq,p),tSR):
        return
    return freq""",
    "Snippet 15.5:": """import numpy as np,scipy.stats as ss
#---------------------------------------
def mixGaussians(mu1,mu2,sigma1,sigma2,prob1,nObs):
    # Random draws from a mixture of gaussians
    ret1=np.random.normal(mu1,sigma1,size=int(nObs*prob1))
    ret2=np.random.normal(mu2,sigma2,size=int(nObs)-ret1.shape[0])
    ret=np.append(ret1,ret2,axis=0)
    np.random.shuffle(ret)
    return ret
#---------------------------------------
def probFailure(ret,freq,tSR):
    # Derive probability that strategy may fail
    rPos,rNeg=ret[ret>0].mean(),ret[ret<=0].mean()
    p=ret[ret>0].shape[0]/float(ret.shape[0])
    thresP=binHR(rNeg,rPos,freq,tSR)
    risk=ss.norm.cdf(thresP,p,p*(1-p)) # approximation to bootstrap
    return risk
#---------------------------------------
def main():
    #1) Parameters
    mu1,mu2,sigma1,sigma2,prob1,nObs=.05,-.1,.05,.1,.75,2600
    tSR,freq=2.,260
    #2) Generate sample from mixture
    ret=mixGaussians(mu1,mu2,sigma1,sigma2,prob1,nObs)
    #3) Compute prob failure
    probF=probFailure(ret,freq,tSR)
    print 'Prob strategy will fail',probF
    return
#---------------------------------------
if __name__=='__main__':main()""",
}


CHAPTER_16_CODE_OVERRIDES: dict[str, str] = {
    "Snippet 16.4:": """import matplotlib.pyplot as mpl
import scipy.cluster.hierarchy as sch,random,numpy as np,pandas as pd
#---------------------------------------
def getIVP(cov,**kargs):
    # Compute the inverse-variance portfolio
    ivp=1./np.diag(cov)
    ivp/=ivp.sum()
    return ivp
#---------------------------------------
def getClusterVar(cov,cItems):
    # Compute variance per cluster
    cov_=cov.loc[cItems,cItems] # matrix slice
    w_=getIVP(cov_).reshape(-1,1)
    cVar=np.dot(np.dot(w_.T,cov_),w_)[0,0]
    return cVar
#---------------------------------------
def getQuasiDiag(link):
    # Sort clustered items by distance
    link=link.astype(int)
    sortIx=pd.Series([link[-1,0],link[-1,1]])
    numItems=link[-1,3] # number of original items
    while sortIx.max()>=numItems:
        sortIx.index=range(0,sortIx.shape[0]*2,2) # make space
        df0=sortIx[sortIx>=numItems] # find clusters
        i=df0.index;j=df0.values-numItems
        sortIx[i]=link[j,0] # item 1
        df0=pd.Series(link[j,1],index=i+1)
        sortIx=sortIx.append(df0) # item 2
        sortIx=sortIx.sort_index() # re-sort
        sortIx.index=range(sortIx.shape[0]) # re-index
    return sortIx.tolist()
#---------------------------------------
def getRecBipart(cov,sortIx):
    # Compute HRP alloc
    w=pd.Series(1,index=sortIx)
    cItems=[sortIx] # initialize all items in one cluster
    while len(cItems)>0:
        cItems=[i[j:k] for i in cItems for j,k in ((0,len(i)/2), \\
             (len(i)/2,len(i))) if len(i)>1] # bi-section
        for i in xrange(0,len(cItems),2): # parse in pairs
             cItems0=cItems[i] # cluster 1
             cItems1=cItems[i+1] # cluster 2
             cVar0=getClusterVar(cov,cItems0)
             cVar1=getClusterVar(cov,cItems1)
             alpha=1-cVar0/(cVar0+cVar1)
             w[cItems0]*=alpha # weight 1
             w[cItems1]*=1-alpha # weight 2
    return w
#---------------------------------------
def correlDist(corr):
    # A distance matrix based on correlation, where 0<=d[i,j]<=1
    # This is a proper distance metric
    dist=((1-corr)/2.)**.5 # distance matrix
    return dist
#---------------------------------------
def plotCorrMatrix(path,corr,labels=None):
    # Heatmap of the correlation matrix
    if labels is None:labels=[]
    mpl.pcolor(corr)
    mpl.colorbar()
    mpl.yticks(np.arange(.5,corr.shape[0]+.5),labels)
    mpl.xticks(np.arange(.5,corr.shape[0]+.5),labels)
    mpl.savefig(path)
    mpl.clf();mpl.close() # reset pylab
    return
#---------------------------------------
def generateData(nObs,size0,size1,sigma1):
    # Time series of correlated variables
    #1) generating some uncorrelated data
    np.random.seed(seed=12345);random.seed(12345)
    x=np.random.normal(0,1,size=(nObs,size0)) # each row is a variable
    #2) creating correlation between the variables
    cols=[random.randint(0,size0-1) for i in xrange(size1)]
    y=x[:,cols]+np.random.normal(0,sigma1,size=(nObs,len(cols)))
    x=np.append(x,y,axis=1)
    x=pd.DataFrame(x,columns=range(1,x.shape[1]+1))
    return x,cols
#---------------------------------------
def main():
    #1) Generate correlated data
    nObs,size0,size1,sigma1=10000,5,5,.25
    x,cols=generateData(nObs,size0,size1,sigma1)
    print [(j+1,size0+i) for i,j in enumerate(cols,1)]
    cov,corr=x.cov(),x.corr()
    #2) compute and plot correl matrix
    plotCorrMatrix('HRP3_corr0.png',corr,labels=corr.columns)
    #3) cluster
    dist=correlDist(corr)
    link=sch.linkage(dist,'single')
    sortIx=getQuasiDiag(link)
    sortIx=corr.index[sortIx].tolist() # recover labels
    df0=corr.loc[sortIx,sortIx] # reorder
    plotCorrMatrix('HRP3_corr1.png',df0,labels=df0.columns)
    #4) Capital allocation
    hrp=getRecBipart(cov,sortIx)
    print hrp
    return
#---------------------------------------
if __name__=='__main__':main()""",
    "Snippet 16.5:": """import scipy.cluster.hierarchy as sch,random,numpy as np,pandas as pd,CLA
from HRP import correlDist,getIVP,getQuasiDiag,getRecBipart
#---------------------------------------
def generateData(nObs,sLength,size0,size1,mu0,sigma0,sigma1F):
    # Time series of correlated variables
    #1) generate random uncorrelated data
    x=np.random.normal(mu0,sigma0,size=(nObs,size0))
    #2) create correlation between the variables
    cols=[random.randint(0,size0-1) for i in xrange(size1)]
    y=x[:,cols]+np.random.normal(0,sigma0*sigma1F,size=(nObs,len(cols)))
    x=np.append(x,y,axis=1)
    #3) add common random shock
    point=np.random.randint(sLength,nObs-1,size=2)
    x[np.ix_(point,[cols[0],size0])]=np.array([[-.5,-.5],[2,2]])
    #4) add specific random shock
    point=np.random.randint(sLength,nObs-1,size=2)
    x[point,cols[-1]]=np.array([-.5,2])
    return x,cols
#---------------------------------------
def getHRP(cov,corr):
    # Construct a hierarchical portfolio
    corr,cov=pd.DataFrame(corr),pd.DataFrame(cov)
    dist=correlDist(corr)
    link=sch.linkage(dist,'single')
    sortIx=getQuasiDiag(link)
    sortIx=corr.index[sortIx].tolist() # recover labels
    hrp=getRecBipart(cov,sortIx)
    return hrp.sort_index()
#---------------------------------------
def getCLA(cov,**kargs):
    # Compute CLA's minimum variance portfolio
    mean=np.arange(cov.shape[0]).reshape(-1,1) # Not used by C portf
    lB=np.zeros(mean.shape)
    uB=np.ones(mean.shape)
    cla=CLA.CLA(mean,cov,lB,uB)
    cla.solve()
    return cla.w[-1].flatten()
#---------------------------------------
def hrpMC(numIters=1e4,nObs=520,size0=5,size1=5,mu0=0,sigma0=1e-2, \\
    sigma1F=.25,sLength=260,rebal=22):
    # Monte Carlo experiment on HRP
    methods=[getIVP,getHRP,getCLA]
    stats,numIter={i.__name__:pd.Series() for i in methods},0
    pointers=range(sLength,nObs,rebal)
    while numIter<numIters:
        print numIter
        #1) Prepare data for one experiment
        x,cols=generateData(nObs,sLength,size0,size1,mu0,sigma0,sigma1F)
        r={i.__name__:pd.Series() for i in methods}
        #2) Compute portfolios in-sample
        for pointer in pointers:
            x_=x[pointer-sLength:pointer]
            cov_,corr_=np.cov(x_,rowvar=0),np.corrcoef(x_,rowvar=0)
            #3) Compute performance out-of-sample
            x_=x[pointer:pointer+rebal]
            for func in methods:
                w_=func(cov=cov_,corr=corr_) # callback
                r_=pd.Series(np.dot(x_,w_))
                r[func.__name__]=r[func.__name__].append(r_)
        #4) Evaluate and store results
        for func in methods:
            r_=r[func.__name__].reset_index(drop=True)
            p_=(1+r_).cumprod()
            stats[func.__name__].loc[numIter]=p_.iloc[-1]-1
        numIter+=1
    #5) Report results
    stats=pd.DataFrame.from_dict(stats,orient='columns')
    stats.to_csv('stats.csv')
    df0,df1=stats.std(),stats.var()
    print pd.concat([df0,df1,df1/df1['getHRP']-1],axis=1)
    return
#---------------------------------------
if __name__=='__main__':hrpMC()""",
}


CHAPTER_18_CODE_OVERRIDES: dict[str, str] = {
    "Snippet 18.3:": """def matchLength(msg,i,n):
    # Maximum matched length+1, with overlap.
    # i>=n & len(msg)>=i+n
    subS=''
    for l in xrange(n):
        msg1=msg[i:i+l+1]
        for j in xrange(i-n,i):
            msg0=msg[j:j+l+1]
            if msg1==msg0:
                subS=msg1
                break # search for higher l.
    return len(subS)+1,subS # matched length + 1""",
}

CHAPTER_19_CODE_OVERRIDES: dict[str, str] = {
    "Snippet 19.1:": """def getBeta(series,sl):
    hl=series[['High','Low']].values
    hl=np.log(hl[:,0]/hl[:,1])**2
    hl=pd.Series(hl,index=series.index)
    beta=pd.stats.moments.rolling_sum(hl,window=2)
    beta=pd.stats.moments.rolling_mean(beta,window=sl)
    return beta.dropna()
#---------------------------------------
def getGamma(series):
    h2=pd.stats.moments.rolling_max(series['High'],window=2)
    l2=pd.stats.moments.rolling_min(series['Low'],window=2)
    gamma=np.log(h2.values/l2.values)**2
    gamma=pd.Series(gamma,index=h2.index)
    return gamma.dropna()
#---------------------------------------
def getAlpha(beta,gamma):
    den=3-2*2**.5
    alpha=(2**.5-1)*(beta**.5)/den
    alpha-=(gamma/den)**.5
    alpha[alpha<0]=0 # set negative alphas to 0 (see p.727 of paper)
    return alpha.dropna()
#---------------------------------------
def corwinSchultz(series,sl=1):
    # Note: S<0 iif alpha<0
    beta=getBeta(series,sl)
    gamma=getGamma(series)
    alpha=getAlpha(beta,gamma)
    spread=2*(np.exp(alpha)-1)/(1+np.exp(alpha))
    startTime=pd.Series(series.index[0:spread.shape[0]],index=spread.index)
    spread=pd.concat([spread,startTime],axis=1)
    spread.columns=['Spread','Start_Time'] # 1st loc used to compute beta
    return spread""",
    "Snippet 19.2:": """def getSigma(beta,gamma):
    k2=(8/np.pi)**.5
    den=3-2*2**.5
    sigma=(2**-.5-1)*beta**.5/(k2*den)
    sigma+=(gamma/(k2**2*den))**.5
    sigma[sigma<0]=0
    return sigma""",
}

CHAPTER_20_CODE_OVERRIDES: dict[str, str] = {
    "Snippet 20.4:": """import numpy as np
import multiprocessing as mp
#---------------------------------------
def main1():
    # Path dependency: Multi-threaded implementation
    r,numThreads=np.random.normal(0,.01,size=(1000,10000)),24
    parts=np.linspace(0,r.shape[1],min(numThreads,r.shape[1])+1)
    parts,jobs=np.ceil(parts).astype(int),[]
    for i in xrange(1,len(parts)):
        jobs.append(r[:,parts[i-1]:parts[i]]) # parallel jobs
    pool,out=mp.Pool(processes=numThreads),[]
    outputs=pool.imap_unordered(barrierTouch,jobs)
    for out_ in outputs:
        out.append(out_) # asynchronous response
    pool.close()
    pool.join()
    return
#---------------------------------------
if __name__=='__main__':
    import timeit
    print min(timeit.Timer('main1()',setup='from __main__ import main1').repeat(5,10))""",
    "Snippet 20.7:": """def mpPandasObj(func,pdObj,numThreads=24,mpBatches=1,linMols=True,**kargs):
    '''
    Parallelize jobs, return a DataFrame or Series
    + func: function to be parallelized. Returns a DataFrame
    + pdObj[0]: Name of argument used to pass the molecule
    + pdObj[1]: List of atoms that will be grouped into molecules
    + kargs: any other argument needed by func

    Example: df1=mpPandasObj(func,('molecule',df0.index),24,**kargs)
    '''
    import pandas as pd
    if linMols:
        parts=linParts(len(pdObj[1]),numThreads*mpBatches)
    else:
        parts=nestedParts(len(pdObj[1]),numThreads*mpBatches)
    jobs=[]
    for i in xrange(1,len(parts)):
        job={pdObj[0]:pdObj[1][parts[i-1]:parts[i]],'func':func}
        job.update(kargs)
        jobs.append(job)
    if numThreads==1:
        out=processJobs_(jobs)
    else:
        out=processJobs(jobs,numThreads=numThreads)
    if isinstance(out[0],pd.DataFrame):
        df0=pd.DataFrame()
    elif isinstance(out[0],pd.Series):
        df0=pd.Series()
    else:
        return out
    for i in out:
        df0=df0.append(i)
    df0=df0.sort_index()
    return df0""",
}

CHAPTER_21_CODE_OVERRIDES: dict[str, str] = {
    "Snippet 21.2:": """import numpy as np
from itertools import product
#---------------------------------------
def getAllWeights(k,n):
    #1) Generate partitions
    parts,w,seen=pigeonHole(k,n),None,set()
    #2) Go through partitions
    for part_ in parts:
        w_=np.array(part_)/float(k) # abs(weight) vector
        for prod_ in product([-1,1],repeat=n):
            # add sign
            w_signed_=(w_*prod_).reshape(-1,1)
            key=tuple(w_signed_.ravel())
            if key in seen:
                continue
            seen.add(key)
            if w is None:
                w=w_signed_.copy()
            else:
                w=np.append(w,w_signed_,axis=1)
    return w""",
    "Snippet 21.3:": """import numpy as np
from itertools import product
#---------------------------------------
def evalTCosts(w,params,w0=None):
    # Compute t-costs of a particular trajectory
    tcost=np.zeros(w.shape[1])
    w_=np.zeros(w.shape[0]) if w0 is None else np.asarray(w0).reshape(-1)
    for i in range(tcost.shape[0]):
        c_=params[i]['c']
        tcost[i]=(c_*abs(w[:,i]-w_)**.5).sum()
        w_=w[:,i].copy()
    return tcost
#---------------------------------------
def evalSR(params,w,tcost):
    # Evaluate SR over multiple horizons
    mean,cov=0,0
    for h in range(w.shape[1]):
        params_=params[h]
        mean+=np.dot(w[:,h].T,params_['mean'])[0]-tcost[h]
        cov+=np.dot(w[:,h].T,np.dot(params_['cov'],w[:,h]))
    sr=mean/cov**.5
    return sr
#---------------------------------------
def dynOptPort(params,k=None,w0=None):
    # Dynamic optimal portfolio
    #1) Generate partitions
    if k is None:
        k=params[0]['mean'].shape[0]
    n=params[0]['mean'].shape[0]
    w_all,sr=getAllWeights(k,n),None
    #2) Generate trajectories as cartesian products
    for prod_ in product(w_all.T,repeat=len(params)):
        w_=np.array(prod_).T # concatenate product into a trajectory
        tcost_=evalTCosts(w_,params,w0=w0)
        sr_=evalSR(params,w_,tcost_) # evaluate trajectory
        if sr is None or sr<sr_:
            # store trajectory if better
            sr,w=sr_,w_.copy()
    return w""",
    "Snippet 21.5:": """import numpy as np
#---------------------------------------
def genMean(size):
    # Generate a random vector of means
    rMean=np.random.normal(size=(size,1))
    return rMean
#---------------------------------------
#1) Parameters
size,horizon=3,2
params=[]
for h in range(horizon):
    x=rndMatWithRank(1000,3,3,0.)
    mean_,cov_=genMean(size),np.cov(x,rowvar=False)
    c_=np.random.uniform(size=cov_.shape[0])*np.diag(cov_)**.5
    params.append({'mean':mean_,'cov':cov_,'c':c_})""",
    "Snippet 21.6:": """import numpy as np
#---------------------------------------
def statOptPortf(cov,a):
    # Static optimal portfolio
    # Solution to the "unconstrained" portfolio optimization problem
    cov_inv=np.linalg.inv(cov)
    w=np.dot(cov_inv,a)
    w/=np.dot(np.dot(a.T,cov_inv),a) # np.dot(w.T,a)==1
    w/=abs(w).sum() # re-scale for full investment
    return w
#---------------------------------------
#2) Static optimal portfolios
w_stat=None
for params_ in params:
    w_=statOptPortf(cov=params_['cov'],a=params_['mean'])
    if w_stat is None:
        w_stat=w_.copy()
    else:
        w_stat=np.append(w_stat,w_,axis=1)
tcost_stat=evalTCosts(w_stat,params)
sr_stat=evalSR(params,w_stat,tcost_stat)
print 'static SR:',sr_stat""",
}


def run(command: list[str], cwd: Path = ROOT) -> str:
    return subprocess.check_output(command, cwd=cwd, text=True, encoding="utf-8", errors="replace")


def build_xml() -> ET.Element:
    if TMP.exists():
        shutil.rmtree(TMP)
    TMP.mkdir(parents=True)
    subprocess.run(["pdftohtml", "-q", "-xml", str(PDF), str(XML)], cwd=ROOT, check=True)
    return ET.parse(XML).getroot()


def extract_layout_pages() -> list[list[str]]:
    raw = run(["pdftotext", "-layout", "-enc", "UTF-8", str(PDF), "-"])
    parts = raw.split("\f")
    if parts and not parts[-1].strip():
        parts = parts[:-1]
    pages: list[list[str]] = []
    for part in parts:
        lines = [unicodedata.normalize("NFC", line.rstrip()) for line in part.splitlines()]
        pages.append(lines)
    return pages


def copy_xml_images(root: ET.Element) -> dict[int, list[str]]:
    if MEDIA.exists():
        shutil.rmtree(MEDIA)
    MEDIA.mkdir(parents=True)
    images: dict[int, list[str]] = {}
    for page in root.findall("page"):
        page_no = int(page.attrib["number"])
        for image in page.findall("image"):
            src_attr = image.attrib["src"]
            source = (ROOT / src_attr).resolve()
            if not source.exists():
                source = (TMP / Path(src_attr).name).resolve()
            if not source.exists():
                continue
            target = MEDIA / source.name
            shutil.copy2(source, target)
            images.setdefault(page_no, []).append(f"media/{target.name}")
    return images


def ensure_chapter_04_media() -> None:
    target = MEDIA / "chapter-04-figure-4-3.png"
    prefix = TMP / "chapter-04-figure-4-3-98"
    subprocess.run(
        ["pdftoppm", "-r", "220", "-f", "98", "-l", "98", "-png", str(PDF), str(prefix)],
        cwd=ROOT,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    candidates = sorted(prefix.parent.glob(prefix.name + "-*.png"))
    if not candidates:
        return
    rendered = candidates[0]
    try:
        from PIL import Image

        with Image.open(rendered) as image:
            image.crop((215, 170, 900, 650)).save(target)
    except Exception:
        if rendered.exists():
            shutil.copy2(rendered, target)


def ensure_chapter_05_media() -> None:
    crops = {
        "chapter-05-figure-5-1.png": (105, (95, 150, 770, 550)),
        "chapter-05-figure-5-2.png": (106, (95, 150, 775, 520)),
        "chapter-05-figure-5-3.png": (108, (118, 145, 792, 1180)),
        "chapter-05-figure-5-4.png": (110, (100, 145, 792, 635)),
        "chapter-05-figure-5-5.png": (111, (130, 735, 705, 1155)),
    }
    try:
        from PIL import Image
    except Exception:
        return

    for name, (page, box) in crops.items():
        prefix = TMP / f"{name[:-4]}-{page}"
        rendered = TMP / f"{name[:-4]}-{page}-{page}.png"
        subprocess.run(
            ["pdftoppm", "-r", "144", "-f", str(page), "-l", str(page), "-png", str(PDF), str(prefix)],
            cwd=ROOT,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if not rendered.exists():
            continue
        with Image.open(rendered) as image:
            image.crop(box).save(MEDIA / name)


def ensure_chapter_10_media() -> None:
    target = MEDIA / "chapter-10-figure-10-3.png"
    rendered = TMP / "chapter-10-figure-10-3-175.png"
    subprocess.run(
        ["pdftoppm", "-f", "175", "-l", "175", "-png", str(PDF), str(TMP / "chapter-10-figure-10-3")],
        cwd=ROOT,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        from PIL import Image

        with Image.open(rendered) as image:
            image.crop((95, 120, 810, 585)).save(target)
    except Exception:
        if rendered.exists():
            shutil.copy2(rendered, target)


def ensure_chapter_11_media() -> None:
    crops = {
        "chapter-11-figure-11-1.png": (135, 130, 815, 600),
        "chapter-11-figure-11-2.png": (125, 660, 840, 1185),
    }
    rendered = TMP / "chapter-11-figures-184.png"
    subprocess.run(
        ["pdftoppm", "-r", "150", "-f", "184", "-l", "184", "-png", str(PDF), str(TMP / "chapter-11-figures")],
        cwd=ROOT,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        from PIL import Image

        with Image.open(rendered) as image:
            for name, box in crops.items():
                image.crop(box).save(MEDIA / name)
    except Exception:
        if rendered.exists():
            for name in crops:
                shutil.copy2(rendered, MEDIA / name)


def ensure_chapter_13_media() -> None:
    boxes = {
        "top": (120, 150, 990, 805),
        "lower": (120, 820, 990, 1475),
        "bottom": (120, 850, 990, 1515),
        "figure-13-17": (108, 750, 1008, 1424),
    }
    crops = {
        "chapter-13-figure-13-1.png": (204, "lower"),
        "chapter-13-figure-13-2.png": (205, "top"),
        "chapter-13-figure-13-3.png": (206, "top"),
        "chapter-13-figure-13-4.png": (206, "bottom"),
        "chapter-13-figure-13-5.png": (207, "top"),
        "chapter-13-figure-13-6.png": (208, "top"),
        "chapter-13-figure-13-7.png": (208, "bottom"),
        "chapter-13-figure-13-8.png": (209, "top"),
        "chapter-13-figure-13-9.png": (210, "top"),
        "chapter-13-figure-13-10.png": (210, "bottom"),
        "chapter-13-figure-13-11.png": (211, "top"),
        "chapter-13-figure-13-12.png": (211, "bottom"),
        "chapter-13-figure-13-13.png": (212, "top"),
        "chapter-13-figure-13-14.png": (212, "bottom"),
        "chapter-13-figure-13-15.png": (213, "top"),
        "chapter-13-figure-13-16.png": (213, "bottom"),
        "chapter-13-figure-13-17.png": (214, "figure-13-17"),
        "chapter-13-figure-13-18.png": (215, "top"),
        "chapter-13-figure-13-19.png": (215, "bottom"),
        "chapter-13-figure-13-20.png": (216, "top"),
        "chapter-13-figure-13-21.png": (216, "bottom"),
        "chapter-13-figure-13-22.png": (217, "top"),
        "chapter-13-figure-13-23.png": (217, "bottom"),
        "chapter-13-figure-13-24.png": (218, "top"),
        "chapter-13-figure-13-25.png": (218, "bottom"),
    }
    try:
        from PIL import Image
    except Exception:
        return

    rendered_pages: dict[int, Path] = {}
    for page in sorted({page for page, _ in crops.values()}):
        prefix = TMP / "chapter-13-page"
        rendered = TMP / f"chapter-13-page-{page}.png"
        subprocess.run(
            ["pdftoppm", "-r", "180", "-f", str(page), "-l", str(page), "-png", str(PDF), str(prefix)],
            cwd=ROOT,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if rendered.exists():
            rendered_pages[page] = rendered
    for name, (page, slot) in crops.items():
        rendered = rendered_pages.get(page)
        if rendered is None:
            continue
        with Image.open(rendered) as image:
            image.crop(boxes[slot]).save(MEDIA / name)


def ensure_chapter_15_media() -> None:
    target = MEDIA / "chapter-15-figure-15-1.png"
    rendered = TMP / "chapter-15-figure-15-1-239.png"
    subprocess.run(
        ["pdftoppm", "-f", "239", "-l", "239", "-png", str(PDF), str(TMP / "chapter-15-figure-15-1")],
        cwd=ROOT,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        from PIL import Image

        with Image.open(rendered) as image:
            image.crop((275, 202, 1088, 794)).save(target)
    except Exception:
        if rendered.exists():
            shutil.copy2(rendered, target)


def ensure_chapter_16_media() -> None:
    crops = {
        "chapter-16-figure-16-1.png": (250, (145, 130, 790, 650)),
        "chapter-16-figure-16-3.png": (255, (105, 120, 775, 650)),
        "chapter-16-figure-16-5.png": (259, (105, 120, 775, 650)),
        "chapter-16-figure-16-7-ab.png": (262, (210, 120, 705, 900)),
        "chapter-16-figure-16-7-c.png": (263, (210, 120, 675, 500)),
    }
    try:
        from PIL import Image
    except Exception:
        return

    for name, (page, box) in crops.items():
        prefix = TMP / f"{name[:-4]}-{page}"
        rendered = TMP / f"{name[:-4]}-{page}-{page}.png"
        subprocess.run(
            ["pdftoppm", "-f", str(page), "-l", str(page), "-png", str(PDF), str(prefix)],
            cwd=ROOT,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if not rendered.exists():
            continue
        with Image.open(rendered) as image:
            image.crop(box).save(MEDIA / name)

    name = "chapter-16-figure-16-2.png"
    prefix = TMP / "chapter-16-figure-16-2-252"
    rendered = TMP / "chapter-16-figure-16-2-252-252.png"
    subprocess.run(
        ["pdftoppm", "-r", "220", "-f", "252", "-l", "252", "-png", str(PDF), str(prefix)],
        cwd=ROOT,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if rendered.exists():
        with Image.open(rendered) as image:
            image.crop((151, 199, 1169, 1790)).save(MEDIA / name)


def ensure_chapter_17_media() -> None:
    crops = {
        "chapter-17-figure-17-1.png": (280, (70, 125, 870, 545)),
        "chapter-17-figure-17-2.png": (283, (125, 735, 800, 1215)),
        "chapter-17-figure-17-3.png": (284, (125, 125, 825, 1145)),
    }
    try:
        from PIL import Image
    except Exception:
        return

    for name, (page, box) in crops.items():
        prefix = TMP / f"{name[:-4]}-{page}"
        rendered = TMP / f"{name[:-4]}-{page}-{page}.png"
        subprocess.run(
            ["pdftoppm", "-f", str(page), "-l", str(page), "-png", str(PDF), str(prefix)],
            cwd=ROOT,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if not rendered.exists():
            continue
        with Image.open(rendered) as image:
            image.crop(box).save(MEDIA / name)


def ensure_chapter_18_media() -> None:
    crops = {
        "chapter-18-figure-18-1-ab.png": (299, (120, 145, 790, 1090)),
        "chapter-18-figure-18-1-cd.png": (300, (140, 145, 790, 1090)),
        "chapter-18-figure-18-2.png": (301, (185, 805, 740, 1195)),
    }
    try:
        from PIL import Image
    except Exception:
        return

    for name, (page, box) in crops.items():
        prefix = TMP / f"{name[:-4]}-{page}"
        rendered = TMP / f"{name[:-4]}-{page}-{page}.png"
        subprocess.run(
            ["pdftoppm", "-f", str(page), "-l", str(page), "-png", str(PDF), str(prefix)],
            cwd=ROOT,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if not rendered.exists():
            continue
        with Image.open(rendered) as image:
            image.crop(box).save(MEDIA / name)


def ensure_chapter_19_media() -> None:
    crops = {
        "chapter-19-figure-19-1.png": (315, (105, 135, 780, 585)),
        "chapter-19-figure-19-2.png": (316, (105, 135, 805, 585)),
        "chapter-19-figure-19-3.png": (317, (105, 135, 785, 585)),
    }
    try:
        from PIL import Image
    except Exception:
        return

    for name, (page, box) in crops.items():
        prefix = TMP / f"{name[:-4]}-{page}"
        rendered = TMP / f"{name[:-4]}-{page}-{page}.png"
        subprocess.run(
            ["pdftoppm", "-f", str(page), "-l", str(page), "-png", str(PDF), str(prefix)],
            cwd=ROOT,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if not rendered.exists():
            continue
        with Image.open(rendered) as image:
            image.crop(box).save(MEDIA / name)


def ensure_chapter_20_media() -> None:
    crops = {
        "chapter-20-figure-20-1.png": (334, (145, 755, 765, 1235)),
        "chapter-20-figure-20-2.png": (336, (105, 135, 825, 615)),
    }
    try:
        from PIL import Image
    except Exception:
        return

    for name, (page, box) in crops.items():
        prefix = TMP / f"{name[:-4]}-{page}"
        rendered = TMP / f"{name[:-4]}-{page}-{page}.png"
        subprocess.run(
            ["pdftoppm", "-f", str(page), "-l", str(page), "-png", str(PDF), str(prefix)],
            cwd=ROOT,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if not rendered.exists():
            continue
        with Image.open(rendered) as image:
            image.crop(box).save(MEDIA / name)


def ensure_chapter_21_media() -> None:
    crops = {
        "chapter-21-figure-21-1.png": (349, (135, 130, 755, 570)),
    }
    try:
        from PIL import Image
    except Exception:
        return

    for name, (page, box) in crops.items():
        prefix = TMP / f"{name[:-4]}-{page}"
        rendered = TMP / f"{name[:-4]}-{page}-{page}.png"
        subprocess.run(
            ["pdftoppm", "-f", str(page), "-l", str(page), "-png", str(PDF), str(prefix)],
            cwd=ROOT,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if not rendered.exists():
            continue
        with Image.open(rendered) as image:
            image.crop(box).save(MEDIA / name)


def ensure_chapter_22_media() -> None:
    crops = {
        "chapter-22-figure-22-1.png": (359, (90, 135, 820, 535)),
        "chapter-22-figure-22-3.png": (361, (150, 145, 730, 505)),
        "chapter-22-figure-22-6-ab.png": (369, (70, 140, 795, 1085)),
        "chapter-22-figure-22-6-cd.png": (370, (70, 140, 795, 1045)),
        "chapter-22-figure-22-6-ef.png": (371, (70, 140, 795, 1045)),
    }
    try:
        from PIL import Image
    except Exception:
        return

    for name, (page, box) in crops.items():
        prefix = TMP / f"{name[:-4]}-{page}"
        rendered = TMP / f"{name[:-4]}-{page}-{page}.png"
        subprocess.run(
            ["pdftoppm", "-f", str(page), "-l", str(page), "-png", str(PDF), str(prefix)],
            cwd=ROOT,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if not rendered.exists():
            continue
        with Image.open(rendered) as image:
            image.crop(box).save(MEDIA / name)


def clean_line(line: str) -> str:
    return line.replace("\u00a0", " ").rstrip()


def is_running_header(line: str, is_first_text_line: bool) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if re.fullmatch(r"[0-9ivxlcdmIVXLCDM]+", stripped):
        return True
    if not is_first_text_line:
        return False
    if re.fullmatch(r"\d+\s+[A-Z][A-Z0-9 ,/&'’.-]{6,}", stripped):
        return True
    if re.fullmatch(r"[A-Z][A-Z0-9 ,/&'’.-]{6,}\s+\d+", stripped):
        return True
    return False


def page_body_lines(page_lines: list[str], chapter: Chapter, page_no: int) -> list[str]:
    lines: list[str] = []
    saw_text = False
    for raw in page_lines:
        line = clean_line(raw)
        if not line.strip():
            lines.append("")
            continue
        if is_running_header(line, not saw_text):
            saw_text = True
            continue
        saw_text = True
        if page_no == chapter.start and chapter.slug.startswith("chapter-"):
            if re.fullmatch(r"CHAPTER\s+\d+", line.strip()):
                continue
            if line.strip() == chapter.title:
                continue
        lines.append(line)
    return lines


def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "section"


def is_special_heading(line: str) -> bool:
    return line.strip().upper() in {"EXERCISES", "REFERENCES", "REFERENCE", "BIBLIOGRAPHY", "APPENDICES", "INDEX"}


def chapter_number(chapter: Chapter) -> str | None:
    match = re.match(r"chapter-(\d+)", chapter.slug)
    if not match:
        return None
    return str(int(match.group(1)))


def section_heading_match(line: str, chapter: Chapter) -> re.Match[str] | None:
    match = SECTION_RE.match(line)
    if not match:
        return None
    number, title = match.groups()
    expected = chapter_number(chapter)
    if expected is not None and number.split(".")[0] != expected:
        return None
    if not re.search(r"[A-Za-zÀ-ÿ]", title):
        return None
    if title[:1].islower():
        return None
    return match


def is_visual_artifact_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if re.fullmatch(r"[−–\-0-9.,\s]+", stripped) and len(re.findall(r"\d", stripped)) >= 1:
        return True
    if re.fullmatch(r"(?:\d+(?:\.\d+)?\s+)?n\s*=\s*\d+", stripped):
        return True
    if len(re.findall(r"\d+\.\d+", stripped)) >= 4 and len(re.findall(r"[A-Za-zÀ-ÿ]{2,}", stripped)) <= 1:
        return True
    return False


def is_part_opener_line(line: str) -> bool:
    stripped = line.strip()
    if re.fullmatch(r"PART\s+\d+", stripped):
        return True
    if re.fullmatch(r"CHAPTER\s+\d+", stripped):
        return True
    return False


def is_mathish(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    indent = len(line) - len(line.lstrip(" "))
    if stripped.startswith("r "):
        return False
    if re.match(r"^\[\d{4}", stripped):
        return False
    prose_starts = (
        "where ",
        "and ",
        "or ",
        "if ",
        "Since ",
        "with ",
        "When ",
        "Let ",
        "The ",
        "For ",
        "For example,",
        "First,",
        "Second,",
        "Third,",
        "Fourth,",
        "Fifth,",
        "Finally,",
    )
    if stripped.startswith(prose_starts):
        return False
    math_count = sum(1 for ch in stripped if ch in MATH_CHARS)
    has_formula_operator = bool(re.search(r"\s=\s|arg min|max\{|E0|P\[|∑|∏|√", stripped))
    word_count = len(re.findall(r"[A-Za-z]{3,}", stripped))
    if stripped[:1].islower() and word_count >= 2 and not re.match(r"^[a-zA-Z]\s*=", stripped):
        return False
    if re.search(r"\b(where|thus|because|solution|available|observations|distribution|frequency)\b", stripped, re.I) and word_count >= 2:
        return False
    if word_count > 8:
        return False
    if re.search(r"[.!?]\s+[A-Z]", stripped) and word_count > 3:
        return False
    return (indent >= 16 and (math_count >= 1 or has_formula_operator) and word_count <= 6) or (
        math_count >= 3 and word_count <= 5
    )


def is_table_row_like(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if len(re.split(r"\s{2,}", stripped)) > 1:
        return True
    if re.match(r"^\d+\s+", stripped):
        return True
    if stripped in {"X", "..."}:
        return True
    return False


def is_code_like(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    prose_words = re.findall(r"[A-Za-z]{2,}", stripped)
    if len(prose_words) >= 8 and re.search(r"[.!?]($|\s)", stripped):
        return False
    if stripped.startswith((">>>", "...", "#", "def ", "class ", "return ", "import ", "from ", "print ")):
        return True
    if re.match(r"^(if|elif|else|for|while|try|except|finally|with|assert|raise|yield|continue|break)\b", stripped):
        return True
    if re.match(r"^[A-Za-z_][A-Za-z0-9_,.'\[\]\s]*[+*/-]?=", stripped):
        return True
    if re.search(r"\b[A-Za-z_][A-Za-z0-9_]*\(", stripped):
        return True
    if re.search(r"\.loc\[|\.iloc\[|\.at\[|\.copy\(|\.dropna\(|\.reindex\(", stripped):
        return True
    if stripped.endswith(("\\", ":", ")")) and not re.search(r"[.!?]$", stripped):
        return True
    return False


def is_prose_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if stripped.startswith(("#", ">>>", "...")):
        return False
    if re.match(r"^(if|elif|else|for|while|try|except|finally|with|def|class|return|import|from|print|assert|raise|yield|continue|break)\b", stripped):
        return False
    if re.match(r"^[A-Za-z_][A-Za-z0-9_.,\[\]'\"{}()]*\s*[+*/-]?=", stripped):
        return False
    if re.match(r"^[A-Za-z_][A-Za-z0-9_.]*\(", stripped):
        return False
    words = re.findall(r"[A-Za-z]{2,}", stripped)
    if len(words) >= 8:
        return True
    if len(words) >= 5 and stripped.startswith(("A ", "An ", "The ", "This ", "These ", "It ", "In ", "For ", "Suppose ", "Solving ")):
        return True
    return False


def is_code_continuation_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if is_prose_line(stripped):
        return False
    if leading_spaces(line) == 0:
        return False
    return bool(re.search(r"[=()\[\]{},.:+*/_\\-]", stripped))


def triple_quote_count(line: str) -> int:
    return line.count("'''") + line.count('"""') + line.count("’’’") + line.count("‘‘‘")


def bracket_delta(line: str) -> int:
    quote = ""
    escaped = False
    delta = 0
    for ch in line:
        if quote:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == quote:
                quote = ""
            continue
        if ch in {"'", '"'}:
            quote = ch
            continue
        if ch in "([{":
            delta += 1
        elif ch in ")]}":
            delta -= 1
    return delta


def is_caption_continuation(line: str) -> bool:
    stripped = line.strip()
    if not stripped or is_code_like(line):
        return False
    if len(stripped) > 90:
        return False
    letters = [ch for ch in stripped if ch.isalpha()]
    if not letters:
        return False
    upper_ratio = sum(1 for ch in letters if ch.isupper()) / len(letters)
    return upper_ratio > 0.75


def format_caption(text: str) -> str:
    words = text.split()
    formatted: list[str] = []
    acronyms = {"ADF", "CUSUM", "CV", "DD", "FFD", "HHI", "HPC", "HRP", "IID", "LZ", "MDA", "MDI", "ML", "PCA", "RF", "SFI", "TUW"}
    stopwords = {"A", "AN", "AND", "AS", "AT", "BY", "FOR", "FROM", "IN", "OF", "ON", "OR", "THE", "TO", "WITH"}
    for index, word in enumerate(words):
        clean = re.sub(r"[^A-Za-z]", "", word)
        if any(ch.islower() for ch in word) and any(ch.isupper() for ch in word):
            formatted.append(word)
        elif clean in acronyms:
            formatted.append(word)
        elif index > 0 and clean in stopwords:
            formatted.append(word.lower())
        else:
            formatted.append(word.capitalize() if word.isupper() else word)
    return " ".join(formatted)


def next_significant_event(events: list[tuple[str, int, str]], start: int) -> int | None:
    j = start
    while j < len(events):
        if events[j][0] == "line" and events[j][2].strip():
            return j
        j += 1
    return None


def join_paragraph_lines(lines: list[str]) -> str:
    text = ""
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        if text.endswith("-") and line and line[0].islower():
            text = text[:-1] + line
        elif text:
            text += " " + line
        else:
            text = line
    return re.sub(r"\s+", " ", text).strip()


def emit_paragraph(blocks: list[Block], para: list[str]) -> None:
    if para:
        text = join_paragraph_lines(para)
        if text:
            blocks.append(Block("p", text=text))
        para.clear()


def parse_table(lines: list[str]) -> str:
    rows = [line.rstrip() for line in lines if line.strip()]
    split_rows = [re.split(r"\s{2,}", row.strip()) for row in rows]
    useful = [row for row in split_rows if len(row) > 1]
    if len(useful) < 2:
        return "<pre>" + html.escape("\n".join(rows)) + "</pre>"
    max_cols = max(len(row) for row in useful)
    if max_cols < 2:
        return "<pre>" + html.escape("\n".join(rows)) + "</pre>"
    out = ['<table>']
    header = useful[0]
    out.append("<thead><tr>" + "".join(f"<th>{html.escape(cell)}</th>" for cell in header) + "</tr></thead>")
    out.append("<tbody>")
    for row in useful[1:]:
        cells = row + [""] * (max_cols - len(row))
        out.append("<tr>" + "".join(f"<td>{html.escape(cell)}</td>" for cell in cells[:max_cols]) + "</tr>")
    out.append("</tbody></table>")
    return "\n".join(out)


def table_2_1_html() -> str:
    rows = [
        (
            ["Assets", "Liabilities", "Sales", "Costs/earnings", "Macro variables", "..."],
            ["Price/yield/implied volatility", "Volume", "Dividend/coupons", "Open interest", "Quotes/cancellations", "Aggressor side", "..."],
            ["Analyst recommendations", "Credit ratings", "Earnings expectations", "News sentiment", "..."],
            ["Satellite/CCTV images", "Google searches", "Twitter/chats", "Metadata", "..."],
        )
    ]
    headers = ["Fundamental Data", "Market Data", "Analytics", "Alternative Data"]

    def list_cell(items: list[str]) -> str:
        return "<ul>" + "".join(f"<li>{html.escape(item)}</li>" for item in items) + "</ul>"

    return (
        '<table class="semantic-table">'
        "<thead><tr>"
        + "".join(f"<th>{html.escape(header)}</th>" for header in headers)
        + "</tr></thead><tbody>"
        + "<tr>"
        + "".join(f"<td>{list_cell(list(items))}</td>" for items in rows[0])
        + "</tr></tbody></table>"
    )


def semantic_table(headers: list[str], rows: list[list[str]]) -> str:
    return (
        '<table class="semantic-table">'
        "<thead><tr>"
        + "".join(f"<th>{html.escape(header)}</th>" for header in headers)
        + "</tr></thead><tbody>"
        + "".join(
            "<tr>" + "".join(f"<td>{html.escape(cell)}</td>" for cell in row) + "</tr>"
            for row in rows
        )
        + "</tbody></table>"
    )


def table_1_1_html() -> str:
    headers = ["Part", "Chapter", "Fin. data", "Software", "Hardware", "Math", "Meta-Strat", "Overfitting"]
    rows = [
        ["1", "2", "X", "X", "", "", "", ""],
        ["1", "3", "X", "X", "", "", "", ""],
        ["1", "4", "X", "X", "", "", "", ""],
        ["1", "5", "X", "X", "", "X", "", ""],
        ["2", "6", "", "X", "", "", "", ""],
        ["2", "7", "", "X", "", "", "X", "X"],
        ["2", "8", "", "X", "", "", "X", ""],
        ["2", "9", "", "X", "", "", "X", ""],
        ["3", "10", "", "X", "", "", "X", ""],
        ["3", "11", "", "X", "", "X", "", "X"],
        ["3", "12", "", "X", "", "X", "", "X"],
        ["3", "13", "", "X", "", "X", "", "X"],
        ["3", "14", "", "X", "", "X", "", "X"],
        ["3", "15", "", "X", "", "X", "", "X"],
        ["3", "16", "", "X", "", "X", "X", "X"],
        ["4", "17", "X", "X", "", "X", "", ""],
        ["4", "18", "X", "X", "", "X", "", ""],
        ["4", "19", "X", "X", "", "", "", ""],
        ["5", "20", "", "X", "X", "X", "", ""],
        ["5", "21", "", "X", "X", "X", "", ""],
        ["5", "22", "", "X", "X", "X", "", ""],
    ]
    return semantic_table(headers, rows)


def table_1_2_html() -> str:
    headers = ["#", "Category", "Pitfall", "Solution", "Chapter"]
    rows = [
        ["1", "Epistemological", "The Sisyphus paradigm", "The meta-strategy paradigm", "1"],
        ["2", "Epistemological", "Research through backtesting", "Feature importance analysis", "8"],
        ["3", "Data processing", "Chronological sampling", "The volume clock", "2"],
        ["4", "Data processing", "Integer differentiation", "Fractional differentiation", "5"],
        ["5", "Classification", "Fixed-time horizon labeling", "The triple-barrier method", "3"],
        ["6", "Classification", "Learning side and size simultaneously", "Meta-labeling", "3"],
        ["7", "Classification", "Weighting of non-IID samples", "Uniqueness weighting; sequential bootstrapping", "4"],
        ["8", "Evaluation", "Cross-validation leakage", "Purging and embargoing", "7, 9"],
        ["9", "Evaluation", "Walk-forward (historical) backtesting", "Combinatorial purged cross-validation", "11, 12"],
        ["10", "Evaluation", "Backtest overfitting", "Backtesting on synthetic data; the deflated Sharpe ratio", "10-16"],
    ]
    return semantic_table(headers, rows)


def math_display(tex: str) -> str:
    return '<div class="math display">\\[' + html.escape(tex, quote=False) + "\\]</div>"


def math_inline(tex: str) -> str:
    return '<span class="math inline">\\(' + html.escape(tex, quote=False) + "\\)</span>"


def table_17_1_html() -> str:
    rows = [
        (r"o_1=X^\prime y", r"(2T-1)N"),
        (r"o_2=X^\prime X", r"(2T-1)N^2"),
        (r"o_3=o_2^{-1}", r"N^3+N^2+N"),
        (r"o_4=o_3o_1", r"2N^2-N"),
        (r"o_5=y-Xo_4", r"T+(2N-1)T"),
        (r"o_6=o_5^\prime o_5", r"2T-1"),
        (r"o_7=o_3o_6\frac{1}{T-N}", r"2+N^2"),
        (r"o_8=\frac{o_4[0,0]}{\sqrt{o_7[0,0]}}", r"1"),
    ]
    body = "".join(
        "<tr><td>"
        + math_inline(operation)
        + "</td><td>"
        + math_inline(flops)
        + "</td></tr>"
        for operation, flops in rows
    )
    return (
        '<table class="semantic-table">'
        "<thead><tr><th>Matrix Operation</th><th>FLOPs</th></tr></thead>"
        f"<tbody>{body}</tbody></table>"
    )


GREEK_TEX = {
    "𝛼": r"\alpha",
    "𝛽": r"\beta",
    "𝛾": r"\gamma",
    "𝛿": r"\delta",
    "𝜀": r"\varepsilon",
    "𝜃": r"\theta",
    "𝜆": r"\lambda",
    "𝜇": r"\mu",
    "𝜋": r"\pi",
    "𝜌": r"\rho",
    "𝜎": r"\sigma",
    "𝜏": r"\tau",
    "𝜙": r"\phi",
    "𝜑": r"\varphi",
    "𝜔": r"\omega",
    "Λ": r"\Lambda",
    "Δ": r"\Delta",
}
GREEK_NAMES = {
    "𝛼": "alpha",
    "𝛽": "beta",
    "𝛾": "gamma",
    "𝛿": "delta",
    "𝜀": "varepsilon",
    "𝜃": "theta",
    "𝜆": "lambda",
    "𝜇": "mu",
    "𝜋": "pi",
    "𝜌": "rho",
    "𝜎": "sigma",
    "𝜏": "tau",
    "𝜙": "phi",
    "𝜑": "varphi",
    "𝜔": "omega",
}

MATH_TEXT_REPAIRS: list[tuple[str, str]] = [
    (r"\bp\s*([=<>])\s*12\b", r"p \1 1/2"),
    (r"\bP\[bt\s*=\s*−1\]", r"P[b_t=-1]"),
    (r"\bP\[bt\s*=\s*1\]", r"P[b_t=1]"),
    (r"\bH0\s*:", r"H_0:"),
]

INLINE_MATH_TOKEN_RE = re.compile(
    r"E0?\s*\[[^\[\]]+\]|V\s*\[[^\[\]]+\]|P\s*\[[^\[\]]+\]|"
    r"𝜃\[[^\]]+\]|𝜋[+−-]?|𝜎[^\s,.;)]*|𝜇[^\s,.;)]*|𝜌[^\s,.;)]*|"
    r"\b[xyzmprSPVEX]\[[^\[\]]+\]"
)


def repair_math_text(text: str) -> str:
    repaired = unicodedata.normalize("NFC", text)
    for pattern, replacement in MATH_TEXT_REPAIRS:
        repaired = re.sub(pattern, replacement, repaired)
    return repaired


def texify_math_text(text: str) -> str:
    s = repair_math_text(text)
    s = s.replace("−", "-").replace("–", "-").replace("—", "-")
    s = s.replace("…", r"\ldots")
    s = s.replace("≤", r"\le ")
    s = s.replace("≥", r"\ge ")
    s = s.replace("≠", r"\ne ")
    s = s.replace("≈", r"\approx ")
    s = s.replace("∈", r"\in ")
    s = s.replace("∞", r"\infty ")
    s = s.replace("∼", r"\sim ")
    s = s.replace("′", r"^\prime")
    s = s.replace("∗", r"^*")
    for char, name in GREEK_NAMES.items():
        command = "\\" + name
        s = re.sub(char + "\u0302" + r"\s*([A-Za-z])\s*-?1", lambda match, command=command: rf"\hat{{{command}}}_{{{match.group(1)}-1}}", s)
        s = re.sub(char + "\u0302" + r"\s*([A-Za-z])([0-9])", lambda match, command=command: rf"\hat{{{command}}}_{{{match.group(1)}}}^{match.group(2)}", s)
        s = re.sub(char + "\u0302" + r"\s*([A-Za-z])", lambda match, command=command: rf"\hat{{{command}}}_{{{match.group(1)}}}", s)
        s = s.replace(char + "\u0302", rf"\hat{{{command}}}")
    s = re.sub("\u0302" + r"\s*([A-Za-z])([A-Za-z0-9]*)", lambda match: rf"\hat{{{match.group(1)}{match.group(2)}}}", s)
    s = re.sub(r"([A-Za-z])" + "\u0302", lambda match: rf"\hat{{{match.group(1)}}}", s)
    s = re.sub("\u0303" + r"\s*([A-Za-z])([A-Za-z0-9]*)", lambda match: rf"\tilde{{{match.group(1)}{match.group(2)}}}", s)
    s = re.sub(r"([A-Za-z])" + "\u0303", lambda match: rf"\tilde{{{match.group(1)}}}", s)
    s = s.replace("̃", r"\tilde{}")
    s = s.replace("̂", r"\hat{}")
    s = re.sub(r"Δ([A-Za-z])t", r"\\Delta \1_t", s)
    s = re.sub(r"Δ([A-Za-z])", r"\\Delta \1", s)
    s = re.sub(r"𝜋([+])", r"\\pi^+", s)
    s = re.sub(r"𝜋[-]", r"\\pi^-", s)
    s = re.sub(r"𝜋([A-Za-z]),([A-Za-z0-9]+)", r"\\pi_{\1,\2}", s)
    s = re.sub(r"𝜋([A-Za-z])", r"\\pi_{\1}", s)
    for char, name in GREEK_NAMES.items():
        s = re.sub(char + r"([A-Za-z]),([A-Za-z0-9]+)", rf"\\{name}" + r"_{\1,\2}", s)
        s = re.sub(char + r"([A-Za-z])([0-9])", rf"\\{name}" + r"_{\1}^{\2}", s)
        s = re.sub(char + r"([A-Za-z])", rf"\\{name}" + r"_{\1}", s)
        s = re.sub(char + r"\s*2\b", rf"\\{name}" + r"^2", s)
        s = re.sub(char + r"\s*\^\*", rf"\\{name}" + r"^*", s)
    for char, tex in GREEK_TEX.items():
        s = s.replace(char, tex)
    s = s.replace("√", r"\sqrt{}")
    s = s.replace("∑", r"\sum")
    s = s.replace("∏", r"\prod")
    s = re.sub(r"\bE0\s*\[", r"\\mathbb{E}_0[", s)
    s = re.sub(r"\bE\s*\[", r"\\mathbb{E}[", s)
    s = re.sub(r"\bV\s*\[", r"\\mathbb{V}[", s)
    s = re.sub(r"\bProb\s*\[", r"\\operatorname{Prob}[", s)
    s = re.sub(r"\blog2\s*\[", r"\\log_2[", s)
    s = re.sub(r"\blog2\b", r"\\log_2", s)
    s = re.sub(r"\blog\s*\[", r"\\log[", s)
    s = re.sub(r"\barg\s+max", r"\\arg\\max", s)
    s = re.sub(r"\barg\s+min", r"\\arg\\min", s)
    s = re.sub(r"\bmax\s*\{", r"\\max\\{", s)
    s = re.sub(r"\bmin\s*\{", r"\\min\\{", s)
    s = re.sub(r"\bXi\s*2\b", r"X_i^2", s)
    s = re.sub(r"\bXj\s*2\b", r"X_j^2", s)
    s = re.sub(r"\bXi\b", r"X_i", s)
    s = re.sub(r"\bXj\b", r"X_j", s)
    s = re.sub(r"\byi\b", r"y_i", s)
    s = re.sub(r"\byj\b", r"y_j", s)
    s = re.sub(r"(?<!\\)\bpi\b", r"p_i", s)
    s = re.sub(r"(?<!\\)\bpt\b", r"p_t", s)
    s = re.sub(r"(?<!\\)\bbt\b", r"b_t", s)
    s = re.sub(r"(?<!\\)\bmt\b", r"m_t", s)
    s = re.sub(r"(?<!\\)\but\b", r"u_t", s)
    s = re.sub(r"(?<!\\)\bSt\b", r"S_t", s)
    s = re.sub(r"\bSRR\b", r"\\operatorname{SR}_R", s)
    s = re.sub(r"\bSR\b", r"\\operatorname{SR}", s)
    s = re.sub(r"(?<![\\A-Za-z])([A-Za-z])i,([A-Za-z0-9]+)", r"\1_{i,\2}", s)
    s = re.sub(r"(?<![\\A-Za-z])([A-Za-z])t-?1", r"\1_{t-1}", s)
    s = re.sub(r"(?<![\\A-Za-z])([A-Za-z])t\b", r"\1_t", s)
    s = re.sub(r"(?<![\\A-Za-z])([A-Za-z])n\b", r"\1_n", s)
    s = re.sub(r"(?<![\\A-Za-z])([A-Za-z])j\b", r"\1_j", s)
    s = re.sub(r"(?<![\\A-Za-z])([A-Za-z])i\b", r"\1_i", s)
    s = re.sub(r"([A-Za-z])_t-1\b", r"\1_{t-1}", s)
    s = re.sub(r"\\Delta ([A-Za-z])_t-1\b", r"\\Delta \1_{t-1}", s)
    s = re.sub(r"(\]|[A-Za-z])\s*2\b", r"\1^2", s)
    s = re.sub(r"\\pi\s*\^?2", r"\\pi^2", s)
    s = re.sub(r"\\theta\s*\^?2", r"\\theta^2", s)
    s = re.sub(r"\\sigma([A-Za-z])\^2", r"\\sigma_{\1}^2", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def mathify_general_text(text: str) -> str:
    protected = repair_math_text(text)
    placeholders: dict[str, str] = {}

    def replace(match: re.Match[str]) -> str:
        key = f"\uE000GENMATH{len(placeholders)}\uE001"
        placeholders[key] = math_inline(texify_math_text(match.group(0)))
        return key

    protected = INLINE_MATH_TOKEN_RE.sub(replace, protected)
    escaped = html.escape(protected)
    for key, value in placeholders.items():
        escaped = escaped.replace(key, value)
    return escaped


def formula_raw(lines: list[str]) -> str:
    return "\n".join(line.strip() for line in lines if line.strip())


def formula_sentence_html(raw: str) -> str | None:
    compact = " ".join(raw.split())
    if not compact:
        return ""
    prose_markers = (
        "variance is ",
        "Solving for ",
        "of a bet ",
        "is to realize ",
        "observations drawn ",
        "by noting ",
        "[1991,",
        "Note ",
        "The ",
        "This ",
        "For ",
    )
    if compact.startswith(prose_markers) or (
        re.search(r"\b(where|thus|because|solution|available|distribution|frequency|denote|empirical)\b", compact, re.I)
        and len(re.findall(r"[A-Za-z]{3,}", compact)) >= 2
    ):
        return f"<p>{mathify_general_text(compact)}</p>"
    return None


def is_low_information_formula(raw: str) -> bool:
    compact = " ".join(raw.split())
    if not compact:
        return True
    if compact in {"∑", "√", "∞", "[ ]", "{ }", "∏", "−1", "−1∕", "̂", "̃"}:
        return True
    if re.fullmatch(r"[\[\]{}()|⎧⎨⎩⎫⎬⎭⎪∑∏√̂̃\s.,;:-]+", compact):
        return True
    if len(compact) <= 10 and not re.search(r"[=<>≤≥]", compact) and not re.search(r"[A-Za-z]{2,}", compact):
        return True
    return False


def chapter_formula_override_html(chapter: Chapter, raw: str) -> str | None:
    compact = " ".join(raw.split())
    if chapter.slug == "chapter-20":
        if compact in {"r1 =", "r2 =", "rm =", "B", "Zb W b=1"}:
            return ""
        if compact.startswith(("√ ( ) −1 + 1 + 4 r12", "√ ( 2 ) −1 + 1 + 4 rm−1")):
            return ""
        if compact.startswith("condition 12") or compact.startswith("condition \\frac"):
            return ""
        if compact.startswith("\\tilde{b} defined") or compact.startswith("̃b defined") or compact.startswith("̃ b defined"):
            return ""
    if chapter.slug == "chapter-21":
        if compact.startswith("∑H") or ("SR [r]" in compact and "𝜇" in compact and "𝜔" in compact):
            return math_display(
                r"SR[r]=\frac{\sum_{h=1}^{H}\left(\mu_h^\prime\omega_h-\tau_h[\omega]\right)}"
                r"{\sqrt{\sum_{h=1}^{H}\omega_h^\prime V_h\omega_h}}"
            )
        if compact.startswith("max SR [r]") or compact.startswith("max \\operatorname{SR} [r]"):
            return math_display(
                r"\begin{aligned}"
                r"\max_{\omega}\quad & SR[r]\\"
                r"\text{s.t.}\quad & \sum_{i=1}^{N}|\omega_{i,h}|=1,\quad \forall h=1,\ldots,H."
                r"\end{aligned}"
            )
        if compact.startswith(("s.t. :", ") to x1", r") to x1")):
            return ""
        if compact in {"N", "i=1"}:
            return ""
        if compact.startswith("∈ {-1") or "x{-1, 1}" in compact or "x{−1, 1}" in compact:
            return ""
    if chapter.slug == "chapter-16":
        if compact.startswith("2. If") and "then stop" in compact:
            return ""
        if compact.startswith("⎡ min [0, .5659]"):
            return chapter_16_example_html(
                r"Example 16.4 Updating matrix \(\{\tilde d_{i,j}\}\) with the new cluster \(u\)",
                r"u[1]=(1,2)\to\{\dot d_{i,u[1]}\}=\begin{bmatrix}\min[0,.5659]\\\min[.5659,0]\\\min[.9747,1.1225]\end{bmatrix}=\begin{bmatrix}0\\0\\.9747\end{bmatrix}",
            )
        if compact.startswith(("{d\\tilde{i},j }i,j={3,4} = →", "{d̃ i,j }i,j={3,4} = →")):
            return chapter_16_example_html(
                r"Example 16.6 Recursion in search of remaining clusters",
                r"\{\tilde d_{i,j}\}_{i,j=\{3,4\}}=\begin{bmatrix}0&.9747\\.9747&0\end{bmatrix}\to u[2]=(3,4)\to\text{Stop}",
            )
        if ("If |L_i" in compact and "then stop" in compact) or compact.startswith(("{rho_{i,j}", "{\\rho", "{𝜌", ".2 -.2 1", "⎣.2", "{d_{i,j}", "{di,j", "{d\\tilde{i},j", "{d̃ i,j", "⎢ min", "̃", "u[1] = (1, 2)", "min [.9747", "2. If |L_i", "x=", "d_E[x,y]", "min 𝜔′ V𝜔", "√ [0, 1], di,j", "√ ̃ i , Dj", "√ requirements", "𝜎[X] , y = Y", "d[x, y] = √", "√ √ √ T", "√ √ √ ⎛", "d[x, y] = √ √ 2T", "⎝ =")):
            return ""
    if chapter.slug == "chapter-17":
        if compact.startswith("′ yt = 𝛽t xt + 𝜀t"):
            return math_display(r"y_t=\beta_t^\prime x_t+\varepsilon_t")
        if compact.startswith("yt − 𝛽̂t−1 xt"):
            return ""
        if compact.startswith("𝜔̂ t ="):
            return math_display(r"\hat{\omega}_t=\frac{y_t-\hat{\beta}_{t-1}^{\prime}x_t}{\sqrt{f_t}}")
        if compact.startswith("[ ′( ′ )−1 ] ft ="):
            return math_display(r"f_t=\hat{\sigma}_{\varepsilon}^{2}\left[1+x_t^\prime(X_t^\prime X_t)^{-1}x_t\right]")
        if compact.startswith("𝜎̂ 𝜔2 ="):
            return math_display(r"\hat{\sigma}_{\omega}^{2}=\frac{1}{T-k}\sum_{t=k}^{T}\left(\hat{\omega}_t-\mathbb{E}[\hat{\omega}_t]\right)^2")
        if compact.startswith("Sn,t =") or compact.startswith("( √ )−1 Sn,t"):
            return math_display(r"S_{n,t}=(y_t-y_n)\left(\hat{\sigma}_t\sqrt{t-n}\right)^{-1}")
        if compact.startswith("𝜎̂ t2 ="):
            return math_display(r"\hat{\sigma}_{t}^{2}=(t-1)^{-1}\sum_{i=2}^{t}(\Delta y_i)^2")
        if compact.startswith("√ c𝛼") or compact.startswith("c𝛼 [n, t]"):
            return math_display(r"c_{\alpha}[n,t]=\sqrt{b_{\alpha}+\log[t-n]}")
        if compact.startswith("yt = 𝜌yt−1"):
            return math_display(r"y_t=\rho y_{t-1}+\varepsilon_t")
        if compact.startswith("{ yt−1") or compact.startswith("yt−1 + 𝜀t"):
            return math_display(
                r"H_1:\ y_t=\begin{cases}y_{t-1}+\varepsilon_t,&t=1,\ldots,\tau^*T,\\"
                r"\rho y_{t-1}+\varepsilon_t,&t=\tau^*T+1,\ldots,T,\ \rho>1.\end{cases}"
            )
        if compact.startswith("Δyt = 𝛿yt−1"):
            return math_display(r"\Delta y_t=\delta y_{t-1}D_t[\tau^*]+\varepsilon_t")
        if compact.startswith("𝛿̂ DFC"):
            return math_display(r"DFC_{\tau^*}=\frac{\hat{\delta}}{\hat{\sigma}_{\delta}}")
        if compact.startswith("SDFC ="):
            return math_display(r"SDFC=\sup_{\tau^*\in[\tau_0,1-\tau_0]}\{DFC_{\tau^*}\}")
        if compact.startswith("∑ Δyt = 𝛼") or compact.startswith("Δyt = 𝛼 + 𝛽yt−1"):
            return math_display(r"\Delta y_t=\alpha+\beta y_{t-1}+\sum_{l=1}^{L}\gamma_l\Delta y_{t-l}+\varepsilon_t")
        if compact.startswith("{ } 𝛽̂t0 ,t SADFt"):
            return math_display(r"SADF_t=\sup_{t_0\in[1,t-\tau]}\{ADF_{t_0,t}\}=\sup_{t_0\in[1,t-\tau]}\frac{\hat{\beta}_{t_0,t}}{\hat{\sigma}_{\beta_{t_0,t}}}")
        if compact in {"t0 ∈ [1,t−𝜏] 𝛽t ,t", "t0 \\in [1,t-\\tau] \\beta_{t} ,t"} or (
            "t0" in compact and ("t−𝜏" in compact or "t-\\tau" in compact) and ("𝛽t" in compact or "\\beta_{t}" in compact)
        ):
            return ""
        if compact.startswith("Δlog[yt") or compact.startswith("Δ log[yt"):
            return math_display(r"\Delta\log[y_t]\propto\log[y_{t-1}]")
        if compact.startswith("Δlog[xt") or compact.startswith("Δ log[xt"):
            return math_display(r"\Delta\log[x_t]\propto\log[x_{t-1}]\propto\log[y_{t-1}]")
        if compact.startswith("1 T -𝜏 +2") or compact.startswith("1 T -\\tau +2") or (
            "T -\\tau +2" in compact and "t - \\tau + 1" in compact
        ) or (
            "t − 𝜏 + 1" in compact and ("T −𝜏 +2" in compact or "T − 𝜏 + 2" in compact)
        ):
            return math_display(r"\sum_{t=\tau}^{T}(t-\tau+1)=\frac{1}{2}(T-\tau+2)(T-\tau+1)=\binom{T-\tau+2}{2}")
        if compact.startswith("{\\-∞") or compact.startswith("{\\-\\infty") or compact.startswith("{ −∞"):
            return ""
        if compact.startswith("yt = 𝛼 + 𝛾t + 𝛽t2"):
            return math_display(r"y_t=\alpha+\gamma t+\beta t^2+\varepsilon_t")
        if compact.startswith("log[yt ] = 𝛼 + 𝛾t + 𝛽t2"):
            return math_display(r"\log[y_t]=\alpha+\gamma t+\beta t^2+\varepsilon_t")
        if compact.startswith("{ } |𝛽̂ | | t0 ,t | SMTt"):
            return math_display(r"SMT_t=\sup_{t_0\in[1,t-\tau]}\left\{\frac{|\hat{\beta}_{t_0,t}|}{\hat{\sigma}_{\beta_{t_0,t}}}\right\}")
        if compact.startswith("𝜎̂ 2 ance of 𝛽") or compact.startswith("\\hat{\\sigma} 2\\\\ance"):
            return ""
        if compact.startswith("{ } |𝛽̂t ,t | | 0 | SMTt"):
            return math_display(r"SMT_t=\sup_{t_0\in[1,t-\tau]}\left\{\frac{|\hat{\beta}_{t_0,t}|}{\hat{\sigma}_{\beta_{t_0,t}}(t-t_0)^\varphi}\right\}")
    if chapter.slug == "chapter-18":
        if compact.startswith("∈ Aw of length"):
            return ""
        if compact.startswith("∑ H[X]"):
            return math_display(r"H[X]\equiv-\sum_{x\in A}p[x]\log_2 p[x]")
        if compact.startswith("H[X] R[X]"):
            return math_display(r"R[X]\equiv1-\frac{H[X]}{\log_2\|A\|}")
        if compact.startswith("[ ] f [x, y] MI[X, Y]"):
            return math_display(r"MI[X,Y]=E_{f[x,y]}\left[\log\frac{f[x,y]}{f[x]f[y]}\right]=H[X]+H[Y]-H[X,Y]")
        if compact.startswith("MI[X, Y]"):
            return math_display(r"MI[X,Y]=-\frac{1}{2}\log[1-\rho^2]")
        if compact.startswith("1 ∑ [ ] [ ] Ĥ n,w"):
            return math_display(r"\hat{H}_{n,w}=-\frac{1}{w}\sum_{y_1^w\in A^w}\hat{p}_w[y_1^w]\log_2\hat{p}_w[y_1^w]")
        if compact.startswith("{ } Lin"):
            return math_display(r"L_i^n=1+\max\left\{l\mid x_i^{i+l}=x_j^{j+l}\ \text{for some }i-n\le j\le i-1,\ l\in[0,n]\right\}")
        if compact.startswith("n→∞ log2") or compact.startswith("n→\\infty") or compact.startswith("n\\to\\infty"):
            return "<p>Ornstein and Weiss [1993] formally established that</p>" + math_display(r"\lim_{n\to\infty}\frac{L_i^n}{\log_2[n]}=\frac{1}{H}")
        if compact.startswith("H= log[2𝜋e𝜎 2 ]"):
            return math_display(r"H=\frac{1}{2}\log[2\pi e\sigma^2]")
        if compact in {"n+k−1 ]", "[ ]", "k i=1 log2 [n]", "n i=2 log2 [i]"}:
            return ""
        if compact.startswith("[ ]-1 1 ∑ L_i") or compact.startswith("[ ]−1 1 ∑ Li"):
            return ""
        if compact.startswith("1 ∑ log2") or compact.startswith("∑n log2"):
            return ""
        if compact.startswith("∑ x ="):
            return math_display(r"x=\{x_i\}_{i=1}^{n},\quad p=\{p_i\}_{i=1}^{n},\quad 0\le p_i\le1,\quad \sum_{i=1}^{n}p_i=1")
        if compact.startswith("∑ q Mq [x, p]") or compact.startswith("Mq [x, p]"):
            return math_display(r"M_q[x,p]=\left(\sum_{i=1}^{n}p_i x_i^q\right)^{1/q}")
        if compact.startswith("Mq [p, p]"):
            return math_display(r"M_q[p,p]=\left(\sum_{i=1}^{n}p_i^{q+1}\right)^{1/q}")
        if compact.startswith("𝜕Mq [p,p] 𝜕Nq [p]"):
            return ""
        if compact.startswith("≥ 0, hence"):
            return ""
        if compact.startswith("∑ Shannon") or compact.startswith("Shannon"):
            return math_display(
                r"H[p]=\sum_{i=1}^{n}-p_i\log[p_i]"
                r"=-\log\left[\lim_{q\to0}M_q[p,p]\right]"
                r"=\log\left[\lim_{q\to1}N_q[p]\right]"
            )
        if compact.startswith("h = 1.42") or compact.startswith("q = 1 limit") or compact.startswith("n=1 𝜔") or compact.startswith("n=1 \\omega"):
            return ""
        if compact.startswith("[ f𝜔 ]2i"):
            return math_display(r"\theta_i=\frac{[f_\omega]_i^2\Lambda_{i,i}}{\sum_{n=1}^{N}[f_\omega]_n^2\Lambda_{n,n}}")
        if compact.startswith("1 − ∑Nn=1"):
            return math_display(r"H=1-\frac{1}{N}\exp\left[-\sum_{i=1}^{N}\theta_i\log[\theta_i]\right]")
        if compact.startswith("VPIN =") or ("VPIN" in compact and "2V" in compact and "2v" in compact):
            return math_display(
                r"\begin{aligned}"
                r"VPIN&=\frac{\alpha\mu}{\alpha\mu+2\varepsilon}"
                r"=\frac{\alpha\mu}{V}\\"
                r"&\approx\frac{1}{V}\mathbb{E}\left[\left|2V_{\tau}^{B}-V\right|\right]"
                r"=\mathbb{E}\left[\left|2v_{\tau}^{B}-1\right|\right]"
                r"\end{aligned}"
            )
    if chapter.slug == "chapter-19":
        if compact in {"⎪", "⎩", "St = 1 + e𝛼t", "j=0", "T t=1 Lt", "1e–3", "1e-3", "1e–9", "1e-9", "1e–7", "1e-7", "( )", "[ ]"}:
            return ""
        if compact.startswith("⎧1 if Δpt"):
            return ""
        if compact.startswith("bt ="):
            return math_display(r"b_t=\begin{cases}1,&\text{if }\Delta p_t>0,\\-1,&\text{if }\Delta p_t<0,\\b_{t-1},&\text{if }\Delta p_t=0.\end{cases}")
        if compact.startswith("mt ="):
            return math_display(r"m_t=m_{t-1}+u_t")
        if compact.startswith("[ ] Δmt"):
            return math_display(r"\Delta m_t\sim N(0,\sigma_u^2)")
        if compact.startswith("pt ="):
            return math_display(r"p_t=m_t+b_t c")
        if compact.startswith("𝜎 2 Δpt"):
            return math_display(r"\sigma^2[\Delta p_t]=\mathbb{E}[(\Delta p_t)^2]-\left(\mathbb{E}[\Delta p_t]\right)^2=2c^2+\sigma_u^2")
        if compact.startswith("[ ] 𝜎 Δpt"):
            return math_display(r"\sigma[\Delta p_t,\Delta p_{t-1}]=-c^2")
        if compact.startswith("[ T ( [ ])2 ]"):
            return math_display(r"E\left[\frac{1}{T}\sum_{t=1}^{T}\left(\log\left[\frac{H_t}{L_t}\right]\right)^2\right]=k_1\sigma_{HL}^{2}")
        if compact.startswith("[ T ( [ ])]"):
            return math_display(r"E\left[\frac{1}{T}\sum_{t=1}^{T}\log\left[\frac{H_t}{L_t}\right]\right]=k_2\sigma_{HL}")
        if compact.startswith("2 (e𝛼t"):
            return math_display(r"S_t=\frac{2(e^{\alpha_t}-1)}{1+e^{\alpha_t}}")
        if compact.startswith("St ="):
            return ""
        if compact.startswith("√ √ √ 2𝛽t"):
            return (
                math_display(r"\alpha_t=\frac{\sqrt{2\beta_t}-\sqrt{\beta_t}}{3-2\sqrt{2}}-\sqrt{\frac{\gamma_t}{3-2\sqrt{2}}}")
                + math_display(r"\beta_t=E\left[\sum_{j=0}^{1}\left(\log\left[\frac{H_{t-j}}{L_{t-j}}\right]\right)^2\right]")
            )
        if compact.startswith("[ 1 [ ( )]2 ] ∑ Ht−j") or ("Ht−j" in compact and "Lt−j" in compact):
            return math_display(r"\beta_t=E\left[\sum_{j=0}^{1}\left(\log\left[\frac{H_{t-j}}{L_{t-j}}\right]\right)^2\right]")
        if compact.startswith("Lt−j"):
            return ""
        if compact.startswith("[ ( )] Ht−1,t"):
            return math_display(r"\gamma_t=\left(\log\left[\frac{H_{t-1,t}}{L_{t-1,t}}\right]\right)^2")
        if compact.startswith("𝜇 = p0"):
            return math_display(r"\mu=p_0")
        if compact.startswith("√ 𝜎u2 𝛼"):
            return math_display(r"\alpha=-p_0\sqrt{\frac{\sigma_u^2}{\Sigma_0}}")
        if compact.startswith("1 Σ0 𝜆="):
            return math_display(r"\lambda=\frac{1}{2}\sqrt{\frac{\Sigma_0}{\sigma_u^2}}")
        if compact.startswith("√ 𝜎u2 𝛽"):
            return math_display(r"\beta=\sqrt{\frac{\sigma_u^2}{\Sigma_0}}")
        if compact.startswith("( )2 √ v − p0"):
            return math_display(r"\mathbb{E}[\pi]=\frac{(v-p_0)^2}{2}\sqrt{\frac{\sigma_u^2}{\Sigma_0}}=\frac{1}{4\lambda}(v-p_0)^2")
        if compact.startswith("Δpt = 𝜆"):
            return math_display(r"\Delta p_t=\lambda(b_t V_t)+\varepsilon_t")
        if compact.startswith("| [ ]|"):
            return math_display(r"\left|\Delta\log[\tilde p_{\tau}]\right|=\lambda\sum_{t\in B_{\tau}}(p_tV_t)+\varepsilon_{\tau}")
        if compact.startswith("log ̃pi,𝜏"):
            return math_display(r"\log[\tilde p_{i,\tau}]-\log[\tilde p_{i,\tau-1}]=\lambda_i\sum_{t\in B_{i,\tau}}b_{i,t}\sqrt{p_{i,t}V_{i,t}}+\varepsilon_{i,\tau}")
        if compact == "t∈B_i,τ" or compact == "t∈Bi,𝜏" or compact.startswith("t∈B"):
            return ""
        if compact.startswith("[ ] ( ) [ ( ) ] E St"):
            return math_display(r"E[S_t]=(1-\alpha_t)S_0+\alpha_t\left[\delta_tS_B+(1-\delta_t)S_G\right]")
        if compact.startswith("[ ] [ ] 𝜇𝛼t 𝛿t"):
            return math_display(r"E[B_t]=E[S_t]-\frac{\mu\alpha_t\delta_t}{\varepsilon+\mu\alpha_t\delta_t}\left(E[S_t]-S_B\right)")
        if compact.startswith("[ ] [ ] 𝜇𝛼t 1 − 𝛿t"):
            return math_display(r"E[A_t]=E[S_t]+\frac{\mu\alpha_t(1-\delta_t)}{\varepsilon+\mu\alpha_t(1-\delta_t)}\left(S_G-E[S_t]\right)")
        if compact.startswith("[ ] 𝜇𝛼t 1 − 𝛿t"):
            return math_display(
                r"E[A_t-B_t]=\frac{\mu\alpha_t(1-\delta_t)}{\varepsilon+\mu\alpha_t(1-\delta_t)}(S_G-E[S_t])"
                r"+\frac{\mu\alpha_t\delta_t}{\varepsilon+\mu\alpha_t\delta_t}(E[S_t]-S_B)"
            )
        if compact.startswith("1 [ ] 𝛼t 𝜇"):
            return math_display(r"\delta_t=\frac{1}{2}\Longrightarrow E[A_t-B_t]=\frac{\alpha_t\mu}{\alpha_t\mu+2\varepsilon}(S_G-S_B)")
        if compact.startswith("P[V B"):
            return math_display(
                r"\begin{aligned}"
                r"P[V^B,V^S]&=(1-\alpha)P[V^B,\varepsilon]P[V^S,\varepsilon]\\"
                r"&\quad+\alpha\left(\delta P[V^B,\varepsilon]P[V^S,\mu+\varepsilon]+(1-\delta)P[V^B,\mu+\varepsilon]P[V^S,\varepsilon]\right)"
                r"\end{aligned}"
            )
        if compact.startswith("E V B − V S"):
            return math_display(
                r"E[V^B-V^S]=(1-\alpha)(\varepsilon-\varepsilon)"
                r"+\alpha(1-\delta)((\mu+\varepsilon)-\varepsilon)"
                r"+\alpha\delta(\varepsilon-(\mu+\varepsilon))=\alpha\mu(1-2\delta)"
            )
        if compact.startswith("E[|V B"):
            return math_display(r"E[|V^B-V^S|]\approx\alpha\mu")
        if compact.startswith("| |V − V𝜏S"):
            return math_display(r"\frac{1}{n}\sum_{\tau=1}^{n}|V_{\tau}^{B}-V_{\tau}^{S}|\approx\alpha\mu")
        if compact.startswith("V + V𝜏S"):
            return math_display(r"\frac{1}{n}\sum_{\tau=1}^{n}(V_{\tau}^{B}+V_{\tau}^{S})=V=\alpha\mu+2\varepsilon")
        if compact.startswith("∑n| B S|"):
            return math_display(r"VPIN_{\tau}=\frac{\sum_{\tau=1}^{n}|V_{\tau}^{B}-V_{\tau}^{S}|}{\sum_{\tau=1}^{n}(V_{\tau}^{B}+V_{\tau}^{S})}=\frac{\sum_{\tau=1}^{n}|V_{\tau}^{B}-V_{\tau}^{S}|}{nV}")
        if compact.startswith("𝜏=1 V𝜏"):
            return ""
        if compact.startswith("as 𝜙𝜏") or compact.startswith("as \\phi"):
            return ""
    if chapter.slug == "chapter-15":
        if compact.startswith("nE[Xi ] 2p − 1"):
            return math_display(
                r"\theta[p,n]=\frac{n\mathbb{E}[X_i]}{\sqrt{n\mathbb{V}[X_i]}}="
                r"\underbrace{\frac{2p-1}{2\sqrt{p(1-p)}}}_{\substack{\text{t-value of }p\\\text{under }H_0:p=\frac12}}\sqrt{n}"
            )
        if compact.startswith("t−value of p"):
            return ""
        if compact == "2p−1":
            return ""
        if compact == "2 p(1−p)":
            return ""
        if compact.startswith("( √"):
            return ""
        if compact.startswith("p= 1+ 1−") or compact.startswith("p= 1+ 1-"):
            return math_display(r"p=\frac{1}{2}\left(1+\sqrt{1-\frac{n}{\theta^2+n}}\right)")
        if compact.startswith("nE[Xi ] (𝜋+ − 𝜋− )p + 𝜋−"):
            return math_display(
                r"\theta[p,n,\pi_-,\pi_+]=\frac{n\mathbb{E}[X_i]}{\sqrt{n\mathbb{V}[X_i]}}="
                r"\frac{(\pi_+-\pi_-)p+\pi_-}{(\pi_+-\pi_-)\sqrt{p(1-p)}}\sqrt{n}"
            )
        if compact.startswith("2𝜋+ p+𝜋+"):
            return math_display(
                r"\theta[p,n,-\pi_+,\pi_+]=\frac{2\pi_+p-\pi_+}{2\pi_+\sqrt{p(1-p)}}\sqrt{n}"
                r"=\frac{2p-1}{2\sqrt{p(1-p)}}\sqrt{n}=\theta[p,n]"
            )
        if compact.startswith("2𝜋+ p(1−p)"):
            return ""
        if compact.startswith("√ −b +"):
            return math_display(r"p=\frac{-b+\sqrt{b^2-4ac}}{2a}")
        if compact.startswith("r a ="):
            return math_display(
                r"\begin{aligned}"
                r"a&=(n+\theta^2)(\pi_+-\pi_-)^2\\"
                r"b&=\left[2n\pi_- - \theta^2(\pi_+-\pi_-)\right](\pi_+-\pi_-)\\"
                r"c&=n\pi_-^2"
                r"\end{aligned}"
            )
        if compact == "p𝜃 ∗":
            return ""
    return None


def generic_formula_tex(lines: list[str]) -> str:
    cleaned: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        stripped = re.sub(r"[⎧⎨⎩⎫⎬⎭⎪⎡⎢⎣⎤⎥⎦]", "", stripped)
        stripped = stripped.replace("  ", " ")
        cleaned.append(texify_math_text(stripped))
    if not cleaned:
        return ""
    if len(cleaned) == 1:
        return cleaned[0]
    return r"\begin{aligned}" + r"\\".join(cleaned) + r"\end{aligned}"


def is_suspicious_generic_tex(tex: str) -> bool:
    return bool(
        re.search(
            r"\\sqrt\{\}|\\hat\{\}|\\tilde\{\}|\\sum[A-Za-z0-9]|\\prod[A-Za-z0-9]|"
            r"\\Lambda[a-zA-Z]|[⎛⎜⎟⎝⎠⏟]",
            tex,
        )
    )


def formula_block_html(chapter: Chapter, lines: list[str]) -> str:
    raw = formula_raw(lines)
    override = chapter_formula_override_html(chapter, raw)
    if override is not None:
        return override
    if is_low_information_formula(raw):
        return ""
    sentence = formula_sentence_html(raw)
    if sentence is not None:
        return sentence
    tex = generic_formula_tex(lines)
    if is_suspicious_generic_tex(tex):
        return ""
    return math_display(tex) if tex else ""


CHAPTER_02_INLINE_PATTERNS: list[tuple[str, str]] = [
    (r"\{\(pt\s*,\s*vt\s*\)\}t=1,…,T", r"\{(p_t,v_t)\}_{t=1,\ldots,T}"),
    (r"\{\s*bt\s*\}\s*t=1,…,T", r"\{b_t\}_{t=1,\ldots,T}"),
    (r"\{\s*yt\s*\}\s*t=1,…,T", r"\{y_t\}_{t=1,\ldots,T}"),
    (r"\{Kt\s*\}", r"\{K_t\}"),
    (r"\{ct\s*\}", r"\{c_t\}"),
    (r"\{̃ct\s*\}", r"\{\tilde{c}_t\}"),
    (r"\{vt\s*\}", r"\{v_t\}"),
    (r"\{𝜔t\s*\}", r"\{\omega_t\}"),
    (r"bt\s*∈\s*\{−1,\s*1\}", r"b_t\in\{-1,1\}"),
    (r"B\s*⊆\s*\{1,\s*…\s*,\s*T\}", r"B\subseteq\{1,\ldots,T\}"),
    (r"t\s*∈\s*B", r"t\in B"),
    (r"yt\s*≤", r"y_t\le"),
    (r"St\s*≥\s*h", r"S_t\ge h"),
    (r"≥\s*h", r"\ge h"),
    (r"∈\s*\{−1,\s*1\}", r"\in\{-1,1\}"),
    (r"\[t\s*−\s*1,\s*t\]", r"[t-1,t]"),
    (r"i\s*=\s*1,\s*…\s*,\s*I", r"i=1,\ldots,I"),
    (r"t\s*=\s*1,\s*…\s*,\s*T", r"t=1,\ldots,T"),
    (r"E0\s*\[𝜃T\s*\]", r"\mathbb{E}_0[\theta_T]"),
    (r"E0\s*\[vt\s*\|bt\s*=\s*1\]", r"\mathbb{E}_0[v_t|b_t=1]"),
    (r"E0\s*\[vt\s*\|bt\s*=\s*−1\]", r"\mathbb{E}_0[v_t|b_t=-1]"),
    (r"E0\s*\[vt\s*\]", r"\mathbb{E}_0[v_t]"),
    (r"E0\s*\[T\]", r"\mathbb{E}_0[T]"),
    (r"Et−1\s*\[yt\s*\]", r"\mathbb{E}_{t-1}[y_t]"),
    (r"P\[bt\s*=\s*1\]", r"P[b_t=1]"),
    (r"P\[bt\s*=\s*−1\]", r"P[b_t=-1]"),
    (r"T\s*∗", r"T^*"),
    (r"\b2P\[bt\s*=\s*1\]\s*−\s*1\b", r"2P[b_t=1]-1"),
    (r"\b2v\+\s*−\s*E0\s*\[vt\s*\]", r"2v^+-\mathbb{E}_0[v_t]"),
    (r"\bv\+", r"v^+"),
    (r"\bv−", r"v^-"),
    (r"\bbt\b", r"b_t"),
    (r"\bb0\b", r"b_0"),
    (r"\bbT\b", r"b_T"),
    (r"\bpt\b", r"p_t"),
    (r"\bvt\b", r"v_t"),
    (r"\bSt\b", r"S_t"),
    (r"\bS0\b", r"S_0"),
    (r"\bSt−1\b", r"S_{t-1}"),
    (r"\byt\b", r"y_t"),
    (r"\bK0\b", r"K_0"),
    (r"\bKt\b", r"K_t"),
    (r"\bh\b", r"h"),
    (r"\bhi,t\b", r"h_{i,t}"),
    (r"\bhi,t−1\b", r"h_{i,t-1}"),
    (r"\boi,t\b", r"o_{i,t}"),
    (r"\boi,t\+1\b", r"o_{i,t+1}"),
    (r"\bpi,t\b", r"p_{i,t}"),
    (r"\bvi,t\b", r"v_{i,t}"),
    (r"\bdi,t\b", r"d_{i,t}"),
    (r"𝜃T", r"\theta_T"),
    (r"𝜔t", r"\omega_t"),
    (r"𝜔", r"\omega"),
    (r"𝜎", r"\sigma"),
    (r"𝜑i,t", r"\varphi_{i,t}"),
    (r"𝛿i,t", r"\delta_{i,t}"),
    (r"𝜏i", r"\tau_i"),
    (r"𝜇", r"\mu"),
    (r"𝛽", r"\beta"),
    (r"Λ", r"\Lambda"),
]


def mathify_chapter_02_text(text: str) -> str:
    placeholders: dict[str, str] = {}
    protected = text

    for pattern, tex in sorted(CHAPTER_02_INLINE_PATTERNS, key=lambda item: len(item[0]), reverse=True):
        regex = re.compile(pattern)

        def replace(match: re.Match[str], tex: str = tex) -> str:
            key = f"\uE000MATH{len(placeholders)}\uE001"
            placeholders[key] = math_inline(tex)
            return key

        protected = regex.sub(replace, protected)

    escaped = html.escape(protected)
    for key, value in placeholders.items():
        escaped = escaped.replace(key, value)
    return escaped


def chapter_math_override(chapter: Chapter, math_index: int) -> str | None:
    if chapter.slug == "chapter-02":
        if math_index >= len(CHAPTER_02_MATH_OVERRIDES):
            return None
        return CHAPTER_02_MATH_OVERRIDES[math_index]
    if chapter.slug == "chapter-03":
        if math_index >= len(CHAPTER_03_MATH_OVERRIDES):
            return None
        return CHAPTER_03_MATH_OVERRIDES[math_index]
    if chapter.slug == "chapter-04":
        if math_index >= len(CHAPTER_04_MATH_OVERRIDES):
            return None
        return CHAPTER_04_MATH_OVERRIDES[math_index]
    if chapter.slug == "chapter-05":
        if math_index >= len(CHAPTER_05_MATH_OVERRIDES):
            return None
        return CHAPTER_05_MATH_OVERRIDES[math_index]
    if chapter.slug == "chapter-06":
        if math_index >= len(CHAPTER_06_MATH_OVERRIDES):
            return None
        return CHAPTER_06_MATH_OVERRIDES[math_index]
    if chapter.slug == "chapter-09":
        if math_index >= len(CHAPTER_09_MATH_OVERRIDES):
            return None
        return CHAPTER_09_MATH_OVERRIDES[math_index]
    if chapter.slug == "chapter-10":
        if math_index >= len(CHAPTER_10_MATH_OVERRIDES):
            return None
        return CHAPTER_10_MATH_OVERRIDES[math_index]
    if chapter.slug == "chapter-11":
        if math_index >= len(CHAPTER_11_MATH_OVERRIDES):
            return None
        return CHAPTER_11_MATH_OVERRIDES[math_index]
    if chapter.slug == "chapter-12":
        if math_index >= len(CHAPTER_12_MATH_OVERRIDES):
            return None
        return CHAPTER_12_MATH_OVERRIDES[math_index]
    if chapter.slug == "chapter-13":
        if math_index >= len(CHAPTER_13_MATH_OVERRIDES):
            return ""
        return CHAPTER_13_MATH_OVERRIDES[math_index]
    if chapter.slug == "chapter-14":
        if math_index >= len(CHAPTER_14_MATH_OVERRIDES):
            return ""
        return CHAPTER_14_MATH_OVERRIDES[math_index]
    return None


def chapter_code_override(chapter: Chapter, caption: str) -> str | None:
    overrides: dict[str, str]
    if chapter.slug == "chapter-02":
        overrides = CHAPTER_02_CODE_OVERRIDES
    elif chapter.slug == "chapter-03":
        overrides = CHAPTER_03_CODE_OVERRIDES
    elif chapter.slug == "chapter-04":
        overrides = CHAPTER_04_CODE_OVERRIDES
    elif chapter.slug == "chapter-05":
        overrides = CHAPTER_05_CODE_OVERRIDES
    elif chapter.slug == "chapter-08":
        overrides = CHAPTER_08_CODE_OVERRIDES
    elif chapter.slug == "chapter-09":
        overrides = CHAPTER_09_CODE_OVERRIDES
    elif chapter.slug == "chapter-10":
        overrides = CHAPTER_10_CODE_OVERRIDES
    elif chapter.slug == "chapter-13":
        overrides = CHAPTER_13_CODE_OVERRIDES
    elif chapter.slug == "chapter-14":
        overrides = CHAPTER_14_CODE_OVERRIDES
    elif chapter.slug == "chapter-15":
        overrides = CHAPTER_15_CODE_OVERRIDES
    elif chapter.slug == "chapter-16":
        overrides = CHAPTER_16_CODE_OVERRIDES
    elif chapter.slug == "chapter-18":
        overrides = CHAPTER_18_CODE_OVERRIDES
    elif chapter.slug == "chapter-19":
        overrides = CHAPTER_19_CODE_OVERRIDES
    elif chapter.slug == "chapter-20":
        overrides = CHAPTER_20_CODE_OVERRIDES
    elif chapter.slug == "chapter-21":
        overrides = CHAPTER_21_CODE_OVERRIDES
    else:
        return None
    for prefix, source in overrides.items():
        if caption.startswith(prefix):
            return source
    return None


def chapter_15_figure_html(number: str) -> str:
    figures = {
        "15.1": (
            "media/chapter-15-figure-15-1.png",
            "Figure 15.1: The relation between precision (x-axis) and Sharpe ratio (y-axis) for various bet frequencies (n)",
            "Figure 15.1: The relation between precision (x-axis) and Sharpe ratio (y-axis) for various bet frequencies (n)",
        ),
        "15.2": (
            "media/afml-242_1.jpg",
            "Figure 15.2: Heat-map of the implied precision as a function of "
            + math_inline("n")
            + " and "
            + math_inline(r"\pi_-")
            + ", with "
            + math_inline(r"\pi_+=0.1")
            + " and "
            + math_inline(r"\theta^*=1.5"),
            "Figure 15.2: Heat-map of the implied precision as a function of n and pi_-, with pi_+=0.1 and theta*=1.5",
        ),
        "15.3": (
            "media/afml-243_1.jpg",
            "Figure 15.3: Implied frequency as a function of "
            + math_inline("p")
            + " and "
            + math_inline(r"\pi_-")
            + ", with "
            + math_inline(r"\pi_+=0.1")
            + " and "
            + math_inline(r"\theta^*=1.5"),
            "Figure 15.3: Implied frequency as a function of p and pi_-, with pi_+=0.1 and theta*=1.5",
        ),
    }
    src, caption, alt = figures[number]
    return f'<figure class="book-figure"><img src="{src}" alt="{html.escape(alt)}"><figcaption>{caption}</figcaption></figure>'


def chapter_15_block_figure_html(block: Block) -> str | None:
    if block.caption.startswith("Figure 15.1"):
        return chapter_15_figure_html("15.1")
    return None


def chapter_02_block_figure_html(block: Block) -> str | None:
    if block.caption.startswith("Figure 2.3"):
        caption = "Figure 2.3: CUSUM sampling of a price series"
        return f'<figure class="book-figure"><img src="media/afml-67_1.jpg" alt="{html.escape(caption)}"><figcaption>{html.escape(caption)}</figcaption></figure>'
    return None


def chapter_03_block_figure_html(block: Block) -> str | None:
    if block.caption.startswith("Figure 3.1"):
        caption = "Figure 3.1: Two alternative configurations of the triple-barrier method"
        panels = (
            '<div class="figure-panel">'
            f'<img src="media/afml-74_1.jpg" alt="{html.escape(caption)} panel a">'
            '<span class="panel-label">(a)</span>'
            '</div>'
            '<div class="figure-panel">'
            f'<img src="media/afml-74_2.jpg" alt="{html.escape(caption)} panel b">'
            '<span class="panel-label">(b)</span>'
            '</div>'
        )
        return f'<figure class="book-figure multi-panel"><div class="figure-panels">{panels}</div><figcaption>{html.escape(caption)}</figcaption></figure>'
    if block.src == "media/afml-74_2.jpg" and not block.caption:
        return ""
    return None


def chapter_04_block_figure_html(block: Block) -> str | None:
    figures = {
        "Figure 4.1": ("media/afml-88_1.jpg", "Figure 4.1: Histogram of uniqueness values"),
        "Figure 4.2": ("media/afml-95_1.jpg", "Figure 4.2: Monte Carlo experiment of standard vs. sequential bootstraps"),
        "Figure 4.3": ("media/chapter-04-figure-4-3.png", "Figure 4.3: Piecewise-linear time-decay factors"),
    }
    for prefix, (src, caption) in figures.items():
        if block.caption.startswith(prefix):
            return f'<figure class="book-figure"><img src="{src}" alt="{html.escape(caption)}"><figcaption>{html.escape(caption)}</figcaption></figure>'
    return None


def chapter_05_figure_caption(number: str) -> str:
    captions = {
        "5.1": (
            "Figure 5.1: "
            + math_inline(r"\omega_k")
            + " (y-axis) as "
            + math_inline("k")
            + " increases (x-axis). Each line is associated with a particular value of "
            + math_inline(r"d\in[0,1]")
            + ", in 0.1 increments."
        ),
        "5.2": (
            "Figure 5.2: "
            + math_inline(r"\omega_k")
            + " (y-axis) as "
            + math_inline("k")
            + " increases (x-axis). Each line is associated with a particular value of "
            + math_inline(r"d\in[1,2]")
            + ", in 0.1 increments."
        ),
        "5.3": "Figure 5.3: Fractional differentiation without controlling for weight loss (top plot) and after controlling for weight loss with an expanding window (bottom plot)",
        "5.4": "Figure 5.4: Fractional differentiation after controlling for weight loss with a fixed-width window",
        "5.5": "Figure 5.5: ADF statistic as a function of d, on E-mini S&P 500 futures log-prices",
    }
    return captions[number]


def chapter_05_figure_html(number: str) -> str:
    src = f"media/chapter-05-figure-{number.replace('.', '-')}.png"
    caption = chapter_05_figure_caption(number)
    alt = f"Figure {number}"
    return f'<figure class="book-figure"><img src="{src}" alt="{html.escape(alt)}"><figcaption>{caption}</figcaption></figure>'


def chapter_05_block_figure_html(block: Block) -> str | None:
    for number in ("5.1", "5.2", "5.3", "5.4", "5.5"):
        if block.caption.startswith(f"Figure {number}"):
            return chapter_05_figure_html(number)
    if block.src in {"media/afml-108_2.jpg"} and not block.caption:
        return ""
    return None


def chapter_06_figure_caption(number: str) -> str:
    captions = {
        "6.1": "Figure 6.1: Standard deviation of the bagged prediction",
        "6.2": (
            "Figure 6.2: Accuracy of a bagging classifier as a function of the individual estimator's accuracy "
            + math_inline("P")
            + ", the number of estimators "
            + math_inline("N")
            + ", and "
            + math_inline("k=2")
        ),
        "6.3": "Figure 6.3: AdaBoost decision flow",
    }
    return captions[number]


def chapter_06_figure_html(number: str) -> str:
    figures = {
        "6.1": "media/afml-122_1.jpg",
        "6.2": "media/afml-124_1.jpg",
        "6.3": "media/afml-127_1.jpg",
    }
    caption = chapter_06_figure_caption(number)
    return f'<figure class="book-figure"><img src="{figures[number]}" alt="Figure {number}"><figcaption>{caption}</figcaption></figure>'


def chapter_06_block_figure_html(block: Block) -> str | None:
    for number in ("6.1", "6.2", "6.3"):
        if block.caption.startswith(f"Figure {number}"):
            return chapter_06_figure_html(number)
    return None


def chapter_07_figure_html(number: str) -> str:
    figures = {
        "7.1": ("media/afml-131_1.jpg", "Figure 7.1: Train/test splits in a 5-fold CV scheme"),
        "7.2": ("media/afml-134_1.jpg", "Figure 7.2: Purging overlap in the training set"),
        "7.3": ("media/afml-135_1.jpg", "Figure 7.3: Embargo of post-test train observations"),
    }
    src, caption = figures[number]
    return f'<figure class="book-figure"><img src="{src}" alt="Figure {number}"><figcaption>{html.escape(caption)}</figcaption></figure>'


def chapter_07_block_figure_html(block: Block) -> str | None:
    for number in ("7.1", "7.2", "7.3"):
        if block.caption.startswith(f"Figure {number}"):
            return chapter_07_figure_html(number)
    return None


def chapter_08_figure_html(number: str) -> str:
    figures = {
        "8.1": ("media/afml-147_1.jpg", "Figure 8.1: Scatter plot of eigenvalues (x-axis) and MDI levels (y-axis) in log-log scale"),
        "8.2": ("media/afml-152_1.jpg", "Figure 8.2: MDI feature importance computed on a synthetic dataset"),
        "8.3": ("media/afml-153_1.jpg", "Figure 8.3: MDA feature importance computed on a synthetic dataset"),
        "8.4": ("media/afml-153_2.jpg", "Figure 8.4: SFI feature importance computed on a synthetic dataset"),
    }
    src, caption = figures[number]
    return f'<figure class="book-figure"><img src="{src}" alt="{html.escape(caption)}"><figcaption>{html.escape(caption)}</figcaption></figure>'


def chapter_08_block_figure_html(block: Block) -> str | None:
    for number in ("8.1", "8.2", "8.3", "8.4"):
        if block.caption.startswith(f"Figure {number}"):
            if number in {"8.3", "8.4"}:
                return ""
            return chapter_08_figure_html(number)
    return None


def chapter_10_figure_html(number: str) -> str:
    figures = {
        "10.1": (
            "media/afml-170_1.jpg",
            "Figure 10.1: Bet size from predicted probabilities",
            "Figure 10.1: Bet size from predicted probabilities",
        ),
        "10.2": (
            "media/afml-172_1.jpg",
            "Figure 10.2: Discretization of the bet size, d = 0.2",
            "Figure 10.2: Discretization of the bet size, d = 0.2",
        ),
        "10.3": (
            "media/chapter-10-figure-10-3.png",
            "Figure 10.3:",
            "Bet size versus price divergence for the power function sgn[x]|x|^2 and the sigmoid x(.1+x^2)^-.5",
        ),
    }
    src, caption, alt = figures[number]
    if number == "10.3":
        caption_html = (
            html.escape(caption)
            + " "
            + math_inline(r"f[x]=\operatorname{sgn}[x]|x|^2")
            + " (concave to convex) and "
            + math_inline(r"f[x]=x(.1+x^2)^{-.5}")
            + " (convex to concave)"
        )
    else:
        caption_html = html.escape(caption)
    return f'<figure class="book-figure"><img src="{src}" alt="{html.escape(alt)}"><figcaption>{caption_html}</figcaption></figure>'


def chapter_10_block_figure_html(block: Block) -> str | None:
    for number in ("10.1", "10.2", "10.3"):
        if block.caption.startswith(f"Figure {number}"):
            return ""
    return None


def chapter_16_figure_html(number: str) -> str:
    figures = {
        "16.1": (
            ["media/chapter-16-figure-16-1.png"],
            "Figure 16.1: Visualization of Markowitz’s curse",
        ),
        "16.2": (
            ["media/chapter-16-figure-16-2.png"],
            "Figure 16.2: The complete-graph (top) and the tree-graph (bottom) structures",
        ),
        "16.3": (
            ["media/chapter-16-figure-16-3.png"],
            "Figure 16.3: Sequence of cluster formation",
        ),
        "16.4": (
            ["media/afml-258_1.jpg"],
            "Figure 16.4: Heat-map of original covariance matrix",
        ),
        "16.5": (
            ["media/chapter-16-figure-16-5.png"],
            "Figure 16.5: Dendogram of cluster formation",
        ),
        "16.7": (
            ["media/chapter-16-figure-16-7-ab.png", "media/chapter-16-figure-16-7-c.png"],
            "Figure 16.7: (a) Time series of allocations for IVP; (b) HRP; (c) CLA",
        ),
        "16.8": (
            ["media/afml-264_1.jpg", "media/afml-264_2.jpg"],
            "Figure 16.8: Correlation matrix before and after clustering",
        ),
    }
    srcs, caption = figures[number]
    imgs = "".join(f'<img src="{src}" alt="{html.escape(caption)}">' for src in srcs)
    return f'<figure class="book-figure">{imgs}<figcaption>{html.escape(caption)}</figcaption></figure>'


def chapter_16_block_figure_html(block: Block) -> str | None:
    for number in ("16.1", "16.2", "16.3", "16.4", "16.5", "16.7", "16.8"):
        if block.caption.startswith(f"Figure {number}"):
            if number == "16.7" and "Continued" in block.caption:
                return ""
            return chapter_16_figure_html(number)
    if block.src == "media/afml-264_2.jpg" and not block.caption:
        return ""
    return None


def chapter_17_block_figure_html(block: Block) -> str | None:
    if block.caption.startswith("Figure 17.1"):
        caption = "Figure 17.1: Prices (left y-axis) and SADF (right y-axis) over time"
        return f'<figure class="book-figure"><img src="media/chapter-17-figure-17-1.png" alt="{html.escape(caption)}"><figcaption>{html.escape(caption)}</figcaption></figure>'
    if block.caption.startswith("Figure 17.2"):
        caption = "Figure 17.2: SADF (x-axis) vs CADF (y-axis)"
        return f'<figure class="book-figure"><img src="media/chapter-17-figure-17-2.png" alt="{html.escape(caption)}"><figcaption>{html.escape(caption)}</figcaption></figure>'
    if block.caption.startswith("Figure 17.3"):
        caption = (
            "Figure 17.3: (a) "
            + math_inline(r"(SADF_t-C_{t,q})/\dot C_{t,q}")
            + " over time; (b) "
            + math_inline(r"(SADF_t-C_{t,q})/\dot C_{t,q}")
            + " (y-axis) as a function of "
            + math_inline(r"SADF_t")
            + " (x-axis)"
        )
        return f'<figure class="book-figure"><img src="media/chapter-17-figure-17-3.png" alt="Figure 17.3"><figcaption>{caption}</figcaption></figure>'
    if block.src == "media/afml-284_2.jpg" and not block.caption:
        return ""
    return None


def chapter_18_figure_18_1_html() -> str:
    caption = "Figure 18.1: Distribution of entropy estimates under (a) 10, (b) 7, (c) 5, and (d) 2 letter encodings, on messages of length 100"
    panels = (
        '<div class="figure-panel">'
        f'<img src="media/chapter-18-figure-18-1-ab.png" alt="{html.escape(caption)} panels (a) and (b)">'
        '<span class="panel-label">(a)-(b)</span>'
        '</div>'
        '<div class="figure-panel">'
        f'<img src="media/chapter-18-figure-18-1-cd.png" alt="{html.escape(caption)} panels (c) and (d)">'
        '<span class="panel-label">(c)-(d)</span>'
        '</div>'
    )
    return f'<figure class="book-figure multi-panel"><div class="figure-panels">{panels}</div><figcaption>{html.escape(caption)}</figcaption></figure>'


def chapter_18_block_figure_html(block: Block) -> str | None:
    if block.caption.startswith("Figure 18.1"):
        return ""
    if block.caption.startswith("Figure 18.2"):
        caption = "Figure 18.2: Log effective numbers for a family of randomly generated p arrays"
        return f'<figure class="book-figure"><img src="media/chapter-18-figure-18-2.png" alt="{html.escape(caption)}"><figcaption>{html.escape(caption)}</figcaption></figure>'
    if block.src in {
        "media/afml-299_1.jpg",
        "media/afml-299_2.jpg",
        "media/afml-300_1.jpg",
        "media/afml-300_2.jpg",
        "media/afml-301_1.jpg",
    }:
        return ""
    if "⎢" in stripped or "⎥" in stripped or "⋯" in stripped:
        return ""
    if stripped.startswith("E ") and "Tj |R" in stripped:
        return ""
    return None


def chapter_19_block_figure_html(block: Block) -> str | None:
    if block.caption.startswith("Figure 19.1"):
        caption = "Figure 19.1: Kyle’s Lambdas Computed on E-mini S&P 500 Futures"
        return f'<figure class="book-figure"><img src="media/chapter-19-figure-19-1.png" alt="{html.escape(caption)}"><figcaption>{html.escape(caption)}</figcaption></figure>'
    if block.caption.startswith("Figure 19.2"):
        caption = "Figure 19.2: Amihud’s lambdas estimated on E-mini S&P 500 futures"
        return f'<figure class="book-figure"><img src="media/chapter-19-figure-19-2.png" alt="{html.escape(caption)}"><figcaption>{html.escape(caption)}</figcaption></figure>'
    if block.caption.startswith("Figure 19.3"):
        caption = "Figure 19.3: Hasbrouck’s lambdas estimated on E-mini S&P 500 futures"
        return f'<figure class="book-figure"><img src="media/chapter-19-figure-19-3.png" alt="{html.escape(caption)}"><figcaption>{html.escape(caption)}</figcaption></figure>'
    return None


def chapter_20_block_figure_html(block: Block) -> str | None:
    if block.caption.startswith("Figure 20.1"):
        caption = "Figure 20.1: A linear partition of 20 atomic tasks into 6 molecules"
        return f'<figure class="book-figure"><img src="media/chapter-20-figure-20-1.png" alt="{html.escape(caption)}"><figcaption>{html.escape(caption)}</figcaption></figure>'
    if block.caption.startswith("Figure 20.2"):
        caption = "Figure 20.2: A two-nested loops partition of atoms into molecules"
        return f'<figure class="book-figure"><img src="media/chapter-20-figure-20-2.png" alt="{html.escape(caption)}"><figcaption>{html.escape(caption)}</figcaption></figure>'
    return None


def chapter_21_block_figure_html(block: Block) -> str | None:
    if block.caption.startswith("Figure 21.1"):
        caption = "Figure 21.1: Partitions (1, 2, 3) and (3, 2, 1) must be treated as different"
        return f'<figure class="book-figure"><img src="media/chapter-21-figure-21-1.png" alt="{html.escape(caption)}"><figcaption>{html.escape(caption)}</figcaption></figure>'
    if block.src == "media/afml-349_1.jpg":
        return ""
    return None


def chapter_22_figure_html(number: str) -> str:
    captions = {
        "22.1": "Figure 22.1: Schematic of the Magellan cluster (circa 2010), an example of HPC computer cluster",
        "22.2": "Figure 22.2: The cloud ran scientific applications considerably slower than on HPC systems (circa 2010)",
        "22.3": "Figure 22.3: As the number of cores increases (horizontal axis), the virtualization overhead becomes much more significant (circa 2010)",
        "22.4": "Figure 22.4: Supernova SN 2011fe was discovered 11 hours after first evidence of explosion, as a result of the extensive automation in classification of astronomical observations",
        "22.5": "Figure 22.5: A distributed workflow for studying fusion plasma dynamics",
        "22.7": "Figure 22.7: Apple Stock price on May 6, 2010, along with HHI and VPIN values computed every 5 minutes during the market hours",
        "22.8": "Figure 22.8: Time to process 10-year worth of SP500 quotes data stored in HDF5 files, which takes 21 times longer when the same data is in ASCII files (603.98 seconds versus approximately 3.5 hours)",
        "22.10": "Figure 22.10: Fourier spectrum of trading prices of natural gas futures contracts in 2012. Non-uniform FFT identifies strong presence of activities happening once per day (frequency = 366), twice per day (frequency = 732), and once per minute (frequency = 527040 = 366*24*60).",
    }
    sources = {
        "22.1": ["media/chapter-22-figure-22-1.png"],
        "22.2": ["media/afml-360_1.jpg"],
        "22.3": ["media/chapter-22-figure-22-3.png"],
        "22.4": ["media/afml-365_1.jpg"],
        "22.5": ["media/afml-366_1.jpg"],
        "22.7": ["media/afml-372_1.jpg"],
        "22.8": ["media/afml-373_1.jpg"],
        "22.10": ["media/afml-375_1.jpg"],
    }
    caption = captions[number]
    imgs = "".join(f'<img src="{src}" alt="{html.escape(caption)}">' for src in sources[number])
    return f'<figure class="book-figure">{imgs}<figcaption>{html.escape(caption)}</figcaption></figure>'


def chapter_22_figure_22_6_html() -> str:
    caption = (
        "Figure 22.6: Gradient tree boosting (GBT) appears to follow recent usage too closely and therefore "
        "not able to predict the baseline usage as well as the newly develop method named LTAP. "
        "(a) GTB on Control group. (b) LTAP on Control group. (c) GTB on Passive group. "
        "(d) LTAP on Passive group. (e) GTB on Active group. (f) LTAP on Active group"
    )
    imgs = "".join(
        f'<img src="media/{src}" alt="{html.escape(caption)} panel group">'
        for src in (
            "chapter-22-figure-22-6-ab.png",
            "chapter-22-figure-22-6-cd.png",
            "chapter-22-figure-22-6-ef.png",
        )
    )
    return f'<figure class="book-figure chapter-22-figure-6">{imgs}<figcaption>{html.escape(caption)}</figcaption></figure>'


def chapter_22_block_figure_html(block: Block) -> str | None:
    for number in ("22.1", "22.2", "22.3", "22.4", "22.5", "22.7", "22.8", "22.10"):
        if block.caption.startswith(f"Figure {number}:"):
            if number in {"22.2", "22.3", "22.7", "22.8", "22.10"}:
                return ""
            return chapter_22_figure_html(number)
    if block.caption.startswith("Figure 22.9"):
        caption = "Figure 22.9: The average false positive rates (" + math_inline(r"\alpha") + ") of different classes of futures contracts ordered according to their average."
        return f'<figure class="book-figure"><img src="media/afml-374_1.jpg" alt="Figure 22.9"><figcaption>{caption}</figcaption></figure>'
    if block.caption.startswith("Figure 22.6"):
        return ""
    if block.src in {
        "media/afml-359_1.jpg",
    }:
        return ""
    return None


def is_chapter_02_artifact(text: str) -> bool:
    stripped = text.strip()
    if stripped in {"⎪", "T", "t=1", "i=1", "( )", "⎩ ⎭", "⎧ T ⎫"}:
        return True
    if stripped.startswith("gaps.loc[rollDates[1:]]"):
        return True
    if stripped.startswith("𝜔′ V𝜔 = 𝜔′ WΛW"):
        return True
    if re.fullmatch(r"[⎧⎪⎩⎭⎫{}\[\]∑\s|()]+", stripped):
        return True
    return False


def chapter_16_example_html(caption: str, tex: str) -> str:
    def render_caption(text: str) -> str:
        parts = re.split(r"(\\\(.*?\\\))", text)
        rendered: list[str] = []
        for part in parts:
            if part.startswith(r"\(") and part.endswith(r"\)"):
                rendered.append(math_inline(part[2:-2]))
            else:
                rendered.append(html.escape(part))
        return "".join(rendered)

    return math_display(tex) + f'<p class="example-caption">{render_caption(caption)}</p>'


def chapter_16_appendix_heading(text: str) -> str | None:
    headings = {
        "16.A.1 CORRELATION-BASED METRIC": ("appendix-16-a-1", "16.A.1 Correlation-Based Metric"),
        "16.A.2 INVERSE VARIANCE ALLOCATION": ("appendix-16-a-2", "16.A.2 Inverse Variance Allocation"),
        "16.A.3 REPRODUCING THE NUMERICAL EXAMPLE": ("appendix-16-a-3", "16.A.3 Reproducing the Numerical Example"),
        "16.A.4 REPRODUCING THE MONTE CARLO EXPERIMENT": ("appendix-16-a-4", "16.A.4 Reproducing the Monte Carlo Experiment"),
    }
    item = headings.get(text.strip())
    if item is None:
        return None
    section_id, label = item
    return f'<h3 id="{section_id}">{html.escape(label)}</h3>'


def chapter_01_clean_text(text: str) -> str:
    replacements = {
        "evi- dence": "evidence",
        "iso- lation": "isolation",
        "gradu- ated": "graduated",
        "func- tion": "function",
        "strat- egy": "strategy",
        "com- petitors": "competitors",
        "Labora- tory": "Laboratory",
        "architec- tures": "architectures",
        "largescale": "large-scale",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def chapter_01_p(text: str, class_name: str = "") -> str:
    class_attr = f' class="{class_name}"' if class_name else ""
    return f"<p{class_attr}>{mathify_general_text(chapter_01_clean_text(text))}</p>"


def chapter_01_faq_question(text: str) -> str:
    return f'<p class="faq-question"><strong>{html.escape(text)}</strong></p>'


def chapter_01_faq_answer(*paragraphs: str) -> str:
    return "".join(chapter_01_p(paragraph) for paragraph in paragraphs)


def chapter_01_strategy_list(kind: str) -> str:
    def li(label: str, body: str) -> str:
        return f"<li><strong>{html.escape(label)}:</strong> {mathify_general_text(chapter_01_clean_text(body))}</li>"

    def nested(items: list[str]) -> str:
        return "<ul>" + "".join(f"<li>{mathify_general_text(chapter_01_clean_text(item))}</li>" for item in items) + "</ul>"

    if kind == "data":
        return (
            "<ul>"
            + li("Problem", "Garbage in, garbage out.")
            + li("Solution", "Work with unique, hard-to-manipulate data. If you are the only user of this data, whatever its value, it is all for you.")
            + "<li><strong>How:</strong>"
            + nested(["Chapter 2: Structure your data correctly.", "Chapter 3: Produce informative labels.", "Chapters 4 and 5: Model non-IID series properly.", "Chapters 17-19: Find predictive features."])
            + "</li></ul>"
        )
    if kind == "software-problem":
        return "<ul>" + li("Problem", "A specialized task requires customized tools.") + li("Solution", "Develop your own classes. Using popular libraries means more competitors tapping the same well.") + "</ul>"
    if kind == "software-how":
        return "<ul><li><strong>How:</strong>" + nested(["Chapters 2-22: Throughout the book, for each chapter, we develop our own functions. For your particular problems, you will have to do the same, following the examples in the book."]) + "</li></ul>"
    if kind == "hardware":
        return (
            "<ul>"
            + li("Problem", "ML involves some of the most computationally intensive tasks in all of mathematics.")
            + li("Solution", "Become an HPC expert. If possible, partner with a National Laboratory to build a supercomputer.")
            + "<li><strong>How:</strong>"
            + nested(["Chapters 20 and 22: Learn how to think in terms of multiprocessing architectures. Whenever you code a library, structure it in such a way that functions can be called in parallel. You will find plenty of examples in the book.", "Chapter 21: Develop algorithms for quantum computers."])
            + "</li></ul>"
        )
    if kind == "math":
        return (
            "<ul>"
            + li("Problem", "Mathematical proofs can take years, decades, and centuries. No investor will wait that long.")
            + "<li><strong>Solution:</strong> Use experimental math. Solve hard, intractable problems, not by proof but by experiment. For example, Bailey, Borwein, and Plouffe [1997] found a spigot algorithm for "
            + math_inline(r"\pi")
            + " (pi) without proof, against the prior perception that such mathematical finding would not be possible.</li>"
            + "<li><strong>How:</strong>"
            + nested(["Chapter 5: Familiarize yourself with memory-preserving data transformations.", "Chapters 11-15: There are experimental methods to assess the value of your strategy, with greater reliability than a historical simulation.", "Chapter 16: An algorithm that is optimal in-sample can perform poorly out-of-sample. There is no mathematical proof for investment success. Rely on experimental methods to lead your research.", "Chapters 17 and 18: Apply methods to detect structural breaks, and quantify the amount of information carried by financial series.", "Chapter 20: Learn queuing methods for distributed computing so that you can break apart complex tasks and speed up calculations.", "Chapter 21: Become familiar with discrete methods, used among others by quantum computers, to solve intractable problems."])
            + "</li></ul>"
        )
    if kind == "meta":
        return (
            "<ul>"
            + li("Problem", "Amateurs develop individual strategies, believing that there is such a thing as a magical formula for riches. In contrast, professionals develop methods to mass-produce strategies. The money is not in making a car, it is in making a car factory.")
            + li("Solution", "Think like a business. Your goal is to run a research lab like a factory, where true discoveries are not born out of inspiration, but out of methodic hard work. That was the philosophy of physicist Ernest Lawrence, the founder of the first U.S. National Laboratory.")
            + "<li><strong>How:</strong>"
            + nested(["Chapters 7-9: Build a research process that identifies features relevant across asset classes, while dealing with multi-collinearity of financial features.", "Chapter 10: Combine multiple predictions into a single bet.", "Chapter 16: Allocate funds to strategies using a robust method that performs well out-of-sample."])
            + "</li></ul>"
        )
    if kind == "overfitting":
        return (
            "<ul>"
            + li("Problem", "Standard cross-validation methods fail in finance. Most discoveries in finance are false, due to multiple testing and selection bias.")
            + "<li><strong>Solution:</strong>"
            + nested(["Whatever you do, always ask yourself in what way you may be overfitting. Be skeptical about your own work, and constantly challenge yourself to prove that you are adding value.", "Overfitting is unethical. It leads to promising outcomes that cannot be delivered. When done knowingly, overfitting is outright scientific fraud. The fact that many academics do it does not make it right: They are not risking anyone's wealth, not even theirs.", "It is also a waste of your time, resources, and opportunities. Besides, the industry only pays for out-of-sample returns. You will only succeed after you have created substantial wealth for your investors."])
            + "</li><li><strong>How:</strong>"
            + nested(["Chapters 11-15: There are three backtesting paradigms, of which historical simulation is only one. Each backtest is always overfit to some extent, and it is critical to learn to quantify by how much.", "Chapter 16: Learn robust techniques for asset allocation that do not overfit in-sample signals at the expense of out-of-sample performance."])
            + "</li></ul>"
        )
    return ""


def chapter_01_faq_html(group: str) -> str:
    if group == "automation":
        return (
            chapter_01_faq_question("How can ML algorithms be useful in finance?")
            + chapter_01_faq_answer(
                "Many financial operations require making decisions based on pre-defined rules, like option pricing, algorithmic execution, or risk monitoring. This is where the bulk of automation has taken place so far, transforming the financial markets into ultra-fast, hyper-connected networks for exchanging information. In performing these tasks, machines were asked to follow the rules as fast as possible. High-frequency trading is a prime example. See Easley, López de Prado, and O'Hara [2013] for a detailed treatment of the subject.",
                "The algorithmization of finance is unstoppable. Between June 12, 1968, and December 31, 1968, the NYSE was closed every Wednesday, so that back office could catch up with paperwork. Can you imagine that? We live in a different world today, and in 10 years things will be even better. Because the next wave of automation does not involve following rules, but making judgment calls. As emotional beings, subject to fears, hopes, and agendas, humans are not particularly good at making fact-based decisions, particularly when those decisions involve conflicts of interest. In those situations, investors are better served when a machine makes the calls, based on facts learned from hard data. This not only applies to investment strategy development, but to virtually every area of financial advice: granting a loan, rating a bond, classifying a company, recruiting talent, predicting earnings, forecasting inflation, etc. Furthermore, machines will comply with the law, always, when programmed to do so. If a dubious decision is made, investors can go back to the logs and understand exactly what happened. It is much easier to improve an algorithmic investment process than one relying entirely on humans.",
            )
            + chapter_01_faq_question("How can ML algorithms beat humans at investing?")
            + chapter_01_faq_answer("Do you remember when people were certain that computers would never beat humans at chess? Or Jeopardy!? Poker? Go? Millions of years of evolution (a genetic algorithm) have fine-tuned our ape brains to survive in a hostile 3-dimensional world where the laws of nature are static. Now, when it comes to identifying subtle patterns in a high-dimensional world, where the rules of the game change every day, all that fine-tuning turns out to be detrimental. An ML algorithm can spot patterns in a 100-dimensional world as easily as in our familiar 3-dimensional one. And while we all laugh when we see an algorithm make a silly mistake, keep in mind, algorithms have been around only a fraction of our millions of years. Every day they get better at this, we do not. Humans are slow learners, which puts us at a disadvantage in a fast-changing world like finance.")
        )
    if group == "human":
        return (
            chapter_01_faq_question("Does that mean that there is no space left for human investors?")
            + chapter_01_faq_answer("Not at all. No human is better at chess than a computer. And no computer is better at chess than a human supported by a computer. Discretionary PMs are at a disadvantage when betting against an ML algorithm, but it is possible that the best results are achieved by combining discretionary PMs with ML algorithms. This is what has come to be known as the “quantamental” way. Throughout the book you will find techniques that can be used by quantamental teams, that is, methods that allow you to combine human guesses (inspired by fundamental variables) with mathematical forecasts. In particular, Chapter 3 introduces a new technique called meta-labeling, which allows you to add an ML layer on top of a discretionary one.")
            + chapter_01_faq_question("How does financial ML differ from econometrics?")
            + chapter_01_faq_answer(
                "Econometrics is the application of classical statistical methods to economic and financial series. The essential tool of econometrics is multivariate linear regression, an 18th-century technology that was already mastered by Gauss before 1794 (Stigler [1981]). Standard econometric models do not learn. It is hard to believe that something as complex as 21st-century finance could be grasped by something as simple as inverting a covariance matrix.",
                "Every empirical science must build theories based on observation. If the statistical toolbox used to model these observations is linear regression, the researcher will fail to recognize the complexity of the data, and the theories will be awfully simplistic, useless. I have no doubt in my mind, econometrics is a primary reason economics and finance have not experienced meaningful progress over the past 70 years (Calkin and López de Prado [2014a, 2014b]).",
                "For centuries, medieval astronomers made observations and developed theories about celestial mechanics. These theories never considered non-circular orbits, because they were deemed unholy and beneath God's plan. The prediction errors were so gross, that ever more complex theories had to be devised to account for them. It was not until Kepler had the temerity to consider non-circular (elliptical) orbits that all of the sudden a much simpler general model was able to predict the position of the planets with astonishing accuracy. What if astronomers had never considered non-circular orbits? Well . . . what if economists finally started to consider non-linear functions? Where is our Kepler? Finance does not have a Principia because no Kepler means no Newton.",
                "Financial ML methods do not replace theory. They guide it. An ML algorithm learns patterns in a high-dimensional space without being specifically directed. Once we understand what features are predictive of a phenomenon, we can build a theoretical explanation, which can be tested on an independent dataset. Students of economics and finance would do well enrolling in ML courses, rather than econometrics. Econometrics may be good enough to succeed in financial academia (for now), but succeeding in business requires ML.",
            )
            + chapter_01_faq_question("What do you say to people who dismiss ML algorithms as black boxes?")
            + chapter_01_faq_answer(
                "If you are reading this book, chances are ML algorithms are white boxes to you. They are transparent, well-defined, crystal-clear, pattern-recognition functions. Most people do not have your knowledge, and to them ML is like a magician's box: “Where did that rabbit come from? How are you tricking us, witch?” People mistrust what they do not understand. Their prejudices are rooted in ignorance, for which the Socratic remedy is simple: education. Besides, some of us enjoy using our brains, even though neuroscientists still have not figured out exactly how they work (a black box in itself).",
                "From time to time you will encounter Luddites, who are beyond redemption. Ned Ludd was a weaver from Leicester, England, who in 1779 smashed two knitting frames in an outrage. With the advent of the industrial revolution, mobs infuriated by mechanization sabotaged and destroyed all machinery they could find. Textile workers ruined so much industrial equipment that Parliament had to pass laws making “machine breaking” a capital crime. Between 1811 and 1816, large parts of England were in open rebellion, to the point that there were more British troops fighting Luddites than there were fighting Napoleon on the Iberian Peninsula. The Luddite rebellion ended with brutal suppression through military force. Let us hope that the black box movement does not come to that.",
            )
        )
    if group == "scope":
        return (
            chapter_01_faq_question("Why don’t you discuss specific ML algorithms?")
            + chapter_01_faq_answer("The book is agnostic with regards to the particular ML algorithm you choose. Whether you use convolutional neural networks, AdaBoost, RFs, SVMs, and so on, there are many shared generic problems you will face: data structuring, labeling, weighting, stationary transformations, cross-validation, feature selection, feature importance, overfitting, backtesting, etc. In the context of financial modeling, answering these questions is non-trivial, and framework-specific approaches need to be developed. That is the focus of this book.")
            + chapter_01_faq_question("What other books do you recommend on this subject?")
            + chapter_01_faq_answer("To my knowledge, this is the first book to provide a complete and systematic treatment of ML methods specific for finance: starting with a chapter dedicated to financial data structures, another chapter for labeling of financial series, another for sample weighting, time series differentiation, . . . all the way to a full part devoted to the proper backtesting of investment strategies. To be sure, there are a handful of prior publications (mostly journal articles) that have applied standard ML to financial series, but that is not what this book offers. My goal has been to address the unique nuisances that make financial ML modeling particularly challenging. Like any new subject, it is fast evolving, and the book will be updated as major advances take place. Please contact me at mldp@quantresearch.org if there is any particular topic you would like to see treated in future editions. I will gladly add those chapters, while acknowledging the names of those readers who suggested them.")
            + chapter_01_faq_question("I do not understand some of the sections and chapters. What should I do?")
            + chapter_01_faq_answer("My advice is that you start by reading the references listed at the end of the chapter. When I wrote the book, I had to assume the reader was familiar with the existing literature, or this book would lose its focus. If after reading those references the sections still do not make sense, the likely reason is that they are related to a problem well understood by investment professionals (even if there is no mention of it in the literature).")
        )
    if group == "overfit":
        return (
            chapter_01_faq_answer("For example, Chapter 2 will discuss effective methods to adjust futures prices for the roll, a problem known to most practitioners, even though it is rarely addressed in textbooks. I would encourage you to attend one of my regular seminars, and ask me your question at the end of my talk.")
            + chapter_01_faq_question("Why is the book so fixated on backtest overfitting?")
            + chapter_01_faq_answer(
                "There are two reasons. First, backtest overfitting is arguably the most important open problem in all of mathematical finance. It is our equivalent to “P versus NP” in computer science. If there was a precise method to prevent backtest overfitting, we would be able to take backtests to the bank. A backtest would be almost as good as cash, rather than a sales pitch. Hedge funds would allocate funds to portfolio managers with confidence. Investors would risk less, and would be willing to pay higher fees. Regulators would grant licenses to hedge fund managers on the basis of reliable evidence of skill and knowledge, leaving no space for charlatans. In my opinion, an investments book that does not address this issue is not worth your time. Why would you read a book that deals with CAPM, APT, asset allocation techniques, risk management, etc. when the empirical results that support those arguments were selected without determining their false discovery probabilities?",
                "The second reason is that ML is a great weapon in your research arsenal, and a dangerous one to be sure. If backtest overfitting is an issue in econometric analysis, the flexibility of ML makes it a constant threat to your work. This is particularly the case in finance, because our datasets are shorter, with lower signal-to-noise ratio, and we do not have laboratories where we can conduct experiments while controlling for all environmental variables (López de Prado [2015]). An ML book that does not tackle these concerns can be more detrimental than beneficial to your career.",
            )
            + chapter_01_faq_question("What is the mathematical nomenclature of the book?")
            + chapter_01_faq_answer("When I started to write this book, I thought about assigning one symbol to each mathematical variable or function through all the chapters. That would work well if this book dealt with a single subject, like stochastic optimal control. However this book deals with a wide range of mathematical subjects, each with its own conventions. Readers would find it harder to consult references unless I also followed literature standards, which means that sometimes we must re-use symbols. To prevent any confusion, every chapter explains the nomenclature as it is being used. Most of the math is accompanied by a code snippet, so in case of doubt, please always follow the code.")
            + chapter_01_faq_question("Who wrote Chapter 22?")
            + chapter_01_faq_answer(
                "A popular perception is that ML is a new fascinating technology invented or perfected at IBM, Google, Facebook, Amazon, Netflix, Tesla, etc. It is true that technology firms have become heavy users of ML, especially in recent years. Those firms sponsored some of the most publicized recent ML achievements (like Jeopardy! or Go), which may have reinforced that perception.",
                "However, the reader may be surprised to learn that, in fact, U.S. National Laboratories are among the research centers with the longest track record and experience in using ML. These centers utilized ML before it was cool, and they applied it successfully for many decades to produce astounding scientific discoveries. If predicting what movies Netflix should recommend you to watch next is a worthy endeavor, so it is to understand the rate of expansion of the universe, or forecasting what coastlines will be most impacted by global warming, or preventing a cataclysmic failure of our national power grid. These are just some of the amazing questions that institutions like Berkeley Lab work on every day, quietly but tirelessly, with the help of ML.",
                "In Chapter 22, Drs. Horst Simon and Kesheng Wu offer the perspective of a deputy director and a project leader at a major U.S. National Laboratory specializing in large-scale scientific research involving big data, high-performance computing, and ML. Unlike traditional university settings, National Laboratories achieve scientific breakthroughs by putting together interdisciplinary teams that follow well-devised procedures, with strong division of labor and responsibilities. That kind of research model by production chain was born at Berkeley Lab almost 90 years ago and inspired the meta-strategy paradigm explained in Sections 1.2.2 and 1.3.1.",
            )
        )
    return ""


def chapter_01_paragraph_html(text: str) -> str | None:
    stripped = text.strip()
    if stripped in {"Financial Machine Learning as a Distinct Subject", "PROJECTS USUALLY FAIL", "FAQs 15", "FAQs 17"}:
        return ""
    if stripped == "1 Berkeley Lab, http://www.lbl.gov/about.":
        return '<p class="footnote"><sup>1</sup> Berkeley Lab, <a href="http://www.lbl.gov/about">http://www.lbl.gov/about</a>.</p>'
    if stripped == "2 http://www.numbersleuth.org/worlds-gold/.":
        return '<p class="footnote"><sup>2</sup> <a href="http://www.numbersleuth.org/worlds-gold/">http://www.numbersleuth.org/worlds-gold/</a>.</p>'
    if stripped == "3 http://www.nersc.gov/about.":
        return '<p class="footnote"><sup>3</sup> <a href="http://www.nersc.gov/about">http://www.nersc.gov/about</a>.</p>'
    if stripped.startswith("If you have been asked to develop ML strategies"):
        body = mathify_general_text(chapter_01_clean_text(stripped).replace("PET scans.1", "PET scans.<sup>1</sup>"))
        return "<p>" + body.replace("&lt;sup&gt;1&lt;/sup&gt;", "<sup>1</sup>") + "</p>"
    if stripped.startswith("Mining gold or silver"):
        body = mathify_general_text(chapter_01_clean_text(stripped).replace("century!2", "century!<sup>2</sup>"))
        return "<p>" + body.replace("&lt;sup&gt;2&lt;/sup&gt;", "<sup>2</sup>") + "</p>"
    if stripped.startswith("This station assesses the profitability"):
        return chapter_01_p("This station assesses the profitability of an investment strategy under various scenarios. One of the scenarios of interest is how the strategy would perform if history repeated itself. However, the historical path is merely one of the possible outcomes of a stochastic process, and not necessarily the most likely going forward. Alternative scenarios must be evaluated, consistent with the knowledge of the weaknesses and strengths of a proposed strategy. Team members are data scientists with a deep understanding of empirical and experimental techniques. A good backtester incorporates in his analysis meta-information regarding how the strategy came about. In particular, his analysis must evaluate the probability of backtest overfitting by taking into account the number of trials it took to distill the strategy. The results of this evaluation will not be reused by other stations, for reasons that will become apparent in Chapter 11. Instead, backtest results are communicated to management and not shared with anyone else. Chapters 11-16 discuss the analyses carried out by this station.")
    if stripped.startswith("anyone else. Chapters") or stripped.startswith("but by experiment"):
        return ""
    if stripped.startswith("How can ML algorithms be useful in finance?"):
        return chapter_01_faq_html("automation")
    if stripped.startswith("Does that mean that there is no space left"):
        return chapter_01_faq_html("human")
    if stripped.startswith("people do not have your knowledge"):
        return chapter_01_faq_html("scope")
    if stripped.startswith("literature). For example"):
        return chapter_01_faq_html("overfit")
    if stripped.startswith("in using ML. These centers"):
        return ""
    if stripped.startswith("Dr. Horst Simon"):
        body = mathify_general_text(chapter_01_clean_text(stripped).replace("(NERSC).3", "(NERSC).<sup>3</sup>"))
        return "<p>" + body.replace("&lt;sup&gt;3&lt;/sup&gt;", "<sup>3</sup>") + "</p>"
    cleaned = chapter_01_clean_text(stripped)
    if cleaned != stripped:
        return chapter_01_p(cleaned)
    return None


def chapter_03_clean_text(text: str) -> str:
    replacements = {
        "stoploss": "stop-loss",
        "metalabeling": "meta-labeling",
        "meta- labels": "meta-labels",
        "Remem- ber": "Remember",
        "features samples": "feature samples",
        "condi- tions": "conditions",
        "mul- tiple": "multiple",
        "timeindex": "time index",
    }
    cleaned = text.strip()
    for old, new in replacements.items():
        cleaned = cleaned.replace(old, new)
    return cleaned


def chapter_03_code(text: str) -> str:
    return f"<code>{html.escape(text)}</code>"


def chapter_03_text_html(text: str) -> str:
    rendered = mathify_general_text(chapter_03_clean_text(text))
    label_replacements = {
        "{−1, 0, 1}": math_inline(r"\{-1,0,1\}"),
        "{-1, 0, 1}": math_inline(r"\{-1,0,1\}"),
        "{0,1}": math_inline(r"\{0,1\}"),
        "{0, 1}": math_inline(r"\{0,1\}"),
    }
    for old, new in label_replacements.items():
        rendered = rendered.replace(old, new)
    return rendered


def chapter_03_p(text: str) -> str:
    return f"<p>{chapter_03_text_html(text)}</p>"


def chapter_03_paragraph_html(text: str) -> str | None:
    stripped = text.strip()
    if stripped in {"⎪", "pti,0", "(a)", "(b)"}:
        return ""
    if stripped.startswith("In Chapter 2 we discussed how to produce a matrix X"):
        return (
            "<p>In Chapter 2 we discussed how to produce a matrix "
            + math_inline("X")
            + " of financial features out of an unstructured dataset. Unsupervised learning algorithms can learn the patterns from that matrix "
            + math_inline("X")
            + ", for example whether it contains hierarchical clusters. On the other hand, supervised learning algorithms require that the rows in "
            + math_inline("X")
            + " are associated with an array of labels or values "
            + math_inline("y")
            + ", so that those labels or values can be predicted on unseen feature samples. In this chapter we will discuss ways to label financial data.</p>"
        )
    if stripped.startswith("As it relates to finance, virtually all ML papers label observations"):
        return (
            "<p>As it relates to finance, virtually all ML papers label observations using the fixed-time horizon method. This method can be described as follows. Consider a features matrix "
            + math_inline("X")
            + " with "
            + math_inline("I")
            + " rows, "
            + math_inline(r"\{X_i\}_{i=1,\ldots,I}")
            + ", drawn from some bars with index "
            + math_inline(r"t=1,\ldots,T")
            + ", where "
            + math_inline(r"I\le T")
            + ". Chapter 2, Section 2.5 discussed sampling methods that produce the set of features "
            + math_inline(r"\{X_i\}_{i=1,\ldots,I}")
            + ". An observation "
            + math_inline("X_i")
            + " is assigned a label "
            + math_inline(r"y_i\in\{-1,0,1\}")
            + ":</p>"
        )
    if stripped.startswith("⎩ where 𝜏 is a pre-defined constant threshold"):
        return (
            "<p>where "
            + math_inline(r"\tau")
            + " is a pre-defined constant threshold, "
            + math_inline(r"t_{i,0}")
            + " is the index of the bar immediately after "
            + math_inline("X_i")
            + " takes place, "
            + math_inline(r"t_{i,0}+h")
            + " is the index of the "
            + math_inline("h")
            + "-th bar after "
            + math_inline(r"t_{i,0}")
            + ", and "
            + math_inline(r"r_{t_{i,0},t_{i,0}+h}")
            + " is the price return over a bar horizon "
            + math_inline("h")
            + ":</p>"
        )
    if stripped.startswith("Because the literature almost always works with time bars"):
        return (
            "<p>Because the literature almost always works with time bars, "
            + math_inline("h")
            + " implies a fixed-time horizon. The bibliography section lists multiple ML studies, of which Dixon et al. [2016] is a recent example of this labeling method. Despite its popularity, there are several reasons to avoid this approach in most cases. First, as we saw in Chapter 2, time bars do not exhibit good statistical properties. Second, the same threshold "
            + math_inline(r"\tau")
            + " is applied regardless of the observed volatility. Suppose that "
            + math_inline(r"\tau=1E-2")
            + ", where sometimes we label an observation as "
            + math_inline("y_i=1")
            + " subject to a realized bar volatility of "
            + math_inline(r"\sigma_{t_{i,0}}=1E-4")
            + " (e.g., during the night session), and sometimes "
            + math_inline(r"\sigma_{t_{i,0}}=1E-2")
            + " (e.g., around the open). The large majority of labels will be "
            + math_inline("0")
            + ", even if return "
            + math_inline(r"r_{t_{i,0},t_{i,0}+h}")
            + " was predictable and statistically significant.</p>"
            "<p>In other words, it is a very common error to label observations according to a fixed threshold on time bars. Here are a couple of better alternatives. First, label per a varying threshold "
            + math_inline(r"\sigma_{t_{i,0}}")
            + ", estimated using a rolling exponentially weighted standard deviation of returns. Second, use volume or dollar bars, as their volatilities are much closer to constant (homoscedasticity). But even these two improvements miss a key flaw of the fixed-time horizon method: the path followed by prices. Every investment strategy has stop-loss limits, whether they are self-imposed by the portfolio manager, enforced by the risk department, or triggered by a margin call. It is simply unrealistic to build a strategy that profits from positions that would have been stopped-out by the exchange. That virtually no publication accounts for that when labeling observations tells you something about the current state of the investment literature.</p>"
        )
    if stripped.startswith("As argued in the previous section, in practice we want to set profit taking"):
        return (
            "<p>As argued in the previous section, in practice we want to set profit-taking and stop-loss limits that are a function of the risks involved in a bet. Otherwise, sometimes we will be aiming too high ("
            + math_inline(r"\tau\gg\sigma_{t_{i,0}}")
            + "), and sometimes too low ("
            + math_inline(r"\tau\ll\sigma_{t_{i,0}}")
            + "), considering the prevailing volatility. Snippet 3.1 computes the daily volatility at intraday estimation points, applying a span of "
            + chapter_03_code("span0")
            + " days to an exponentially weighted moving standard deviation. See the pandas documentation for details on the "
            + chapter_03_code("pandas.Series.ewm")
            + " function.</p>"
        )
    if stripped.startswith("Here I will introduce an alternative labeling method"):
        return (
            "<p>Here I will introduce an alternative labeling method that I have not found in the literature. If you are an investment professional, I think you will agree that it makes more sense. I call it the triple-barrier method because it labels an observation according to the first barrier touched out of three barriers. First, we set two horizontal barriers and one vertical barrier. The two horizontal barriers are defined by profit-taking and stop-loss limits, which are a dynamic function of estimated volatility (whether realized or implied). The third barrier is defined in terms of number of bars elapsed since the position was taken (an expiration limit). If the upper barrier is touched first, we label the observation as "
            + math_inline("1")
            + ". If the lower barrier is touched first, we label the observation as "
            + math_inline("-1")
            + ". If the vertical barrier is touched first, we have two choices: the sign of the return, or a "
            + math_inline("0")
            + ".</p>"
            "<p>I personally prefer the former as a matter of realizing a profit or loss within limits, but you should explore whether a "
            + math_inline("0")
            + " works better in your particular problems. You may have noticed that the triple-barrier method is path-dependent. In order to label an observation, we must take into account the entire path spanning "
            + math_inline(r"[t_{i,0},t_{i,0}+h]")
            + ", where "
            + math_inline("h")
            + " defines the vertical barrier (the expiration limit). We will denote "
            + math_inline(r"t_{i,1}")
            + " the time of the first barrier touch, and the return associated with the observed feature is "
            + math_inline(r"r_{t_{i,0},t_{i,1}}")
            + ". For the sake of clarity, "
            + math_inline(r"t_{i,1}\le t_{i,0}+h")
            + " and the horizontal barriers are not necessarily symmetric.</p>"
            "<p>Snippet 3.2 implements the triple-barrier method. The function receives four arguments:</p>"
        )
    if stripped.startswith("Suppose that I = 1E6 and h = 1E3"):
        return (
            "<p>Suppose that "
            + math_inline("I=1E6")
            + " and "
            + math_inline("h=1E3")
            + ", then the number of conditions to evaluate is up to one billion on a single instrument. Many ML tasks are computationally expensive unless you are familiar with multithreading, and this is one of them. Here is where parallel computing comes into play. Chapter 20 discusses a few multiprocessing functions that we will use throughout the book.</p>"
            "<p>Function "
            + chapter_03_code("mpPandasObj")
            + " calls a multiprocessing engine, which is explained in depth in Chapter 20. For the moment, you simply need to know that this function will execute "
            + chapter_03_code("applyPtSlOnT1")
            + " in parallel. Function "
            + chapter_03_code("applyPtSlOnT1")
            + " returns the timestamps at which each barrier is touched (if any). Then, the time of the first touch is the earliest time among the three returned by "
            + chapter_03_code("applyPtSlOnT1")
            + ". Because we must learn the side of the bet, we have passed "
            + chapter_03_code("ptSl=[ptSl,ptSl]")
            + " as argument, and we arbitrarily set the side to be always long (the horizontal barriers are symmetric, so the side is irrelevant to determining the time of the first touch). The output from this function is a pandas dataframe with columns:</p>"
        )
    if stripped.startswith("expensive unless you are familiar with multi-threading"):
        return ""
    if stripped.startswith("Snippet 3.4 shows one way to define a vertical barrier"):
        return (
            "<p>Snippet 3.4 shows one way to define a vertical barrier. For each index in "
            + chapter_03_code("tEvents")
            + ", it finds the timestamp of the next price bar at or immediately after a number of days "
            + chapter_03_code("numDays")
            + ". This vertical barrier can be passed as optional argument "
            + chapter_03_code("t1")
            + " in "
            + chapter_03_code("getEvents")
            + ".</p>"
        )
    if stripped.startswith("Finally, we can label the observations using the getBins function"):
        return (
            "<p>Finally, we can label the observations using the "
            + chapter_03_code("getBins")
            + " function defined in Snippet 3.5. The arguments are the "
            + chapter_03_code("events")
            + " dataframe we just discussed, and the "
            + chapter_03_code("close")
            + " pandas series of prices. The output is a dataframe with columns:</p>"
        )
    if stripped.startswith("Suppose that you have a model for setting the side"):
        return chapter_03_p(stripped)
    if stripped.startswith("Likewise, we need to expand the getBins function"):
        return "<p>Likewise, we need to expand the " + chapter_03_code("getBins") + " function, so that it handles meta-labeling. Snippet 3.7 implements the necessary changes.</p>"
    if stripped.startswith("Now the possible values for labels"):
        return (
            "<p>Now the possible values for labels in "
            + chapter_03_code("out['bin']")
            + " are "
            + math_inline(r"\{0,1\}")
            + ", as opposed to the previous feasible values "
            + math_inline(r"\{-1,0,1\}")
            + ". The ML algorithm will be trained to decide whether to take the bet or pass, a purely binary prediction. When the predicted label is "
            + math_inline("1")
            + ", we can use the probability of this secondary prediction to derive the size of the bet, where the side (sign) of the position has been set by the primary model.</p>"
        )
    if stripped.startswith("Binary classification problems present a trade-off"):
        return (
            "<p>Binary classification problems present a trade-off between type-I errors (false positives) and type-II errors (false negatives). In general, increasing the true positive rate of a binary classifier will tend to increase its false positive rate. The receiver operating characteristic (ROC) curve of a binary classifier measures the cost of increasing the true positive rate, in terms of accepting higher false positive rates.</p>"
        )
    if stripped.startswith("characteristic (ROC) curve"):
        return (
            "<p>Figure 3.2 illustrates the so-called “confusion matrix.” On a set of observations, there are items that exhibit a condition (positives, left rectangle), and items that do not exhibit a condition (negative, right rectangle). A binary classifier predicts that some items exhibit the condition (ellipse), where the TP area contains the true positives and the TN area contains the true negatives. This leads to two kinds of errors: false positives (FP) and false negatives (FN). “Precision” is the ratio between the TP area and the area in the ellipse. “Recall” is the ratio between the TP area and the area in the left rectangle. This notion of recall (aka true positive rate) is in the context of classification problems, the analogous to “power” in the context of hypothesis testing. “Accuracy” is the sum of the TP and TN areas divided by the overall set of items (square). In general, decreasing the FP area comes at a cost of increasing the FN area, because higher precision typically means fewer calls, hence lower recall. Still, there is some combination of precision and recall that maximizes the overall efficiency of the classifier. The F1-score measures the efficiency of a classifier as the harmonic average between precision and recall (more on this in Chapter 14).</p>"
            "<p>Meta-labeling is particularly helpful when you want to achieve higher F1-scores. First, we build a model that achieves high recall, even if the precision is not particularly high. Second, we correct for the low precision by applying meta-labeling to the positives predicted by the primary model.</p>"
        )
    if stripped.startswith("Meta-labeling will increase your F1-score"):
        return chapter_03_p(chapter_03_clean_text(stripped))
    if stripped.startswith("You may have read in the press"):
        return chapter_03_p(chapter_03_clean_text(stripped))
    if stripped.startswith("You can always add a meta-labeling layer"):
        body = chapter_03_text_html(stripped.replace("predictions.1 Many", "predictions.<sup>1</sup> Many"))
        return "<p>" + body.replace("&lt;sup&gt;1&lt;/sup&gt;", "<sup>1</sup>") + "</p>"
    if stripped.startswith("1 You are probably aware"):
        return '<p class="footnote"><sup>1</sup> You are probably aware of at least one large hedge fund that monitors the emotional state of their research analysts on a daily basis.</p>'
    if stripped == "analysts on a daily basis.":
        return ""
    cleaned = chapter_03_clean_text(stripped)
    if cleaned != stripped:
        return chapter_03_p(cleaned)
    return None


def chapter_04_code(text: str) -> str:
    return f"<code>{html.escape(text)}</code>"


def chapter_04_text_html(text: str) -> str:
    replacements = {
        "num- ber": "number",
        "obser- vations": "observations",
        "sequenupdate": "sequence",
        "sequen tial bootstrap": "sequential bootstrap",
        "sequen- tial bootstrap": "sequential bootstrap",
        "sequensequential bootstrap": "sequential bootstrap",
        "can[ be defined]": "can be defined",
        "the[ sample]weights": "the sample weights",
        "sec- tion": "section",
        "timeindex": "time index",
    }
    cleaned = text.strip()
    for old, new in replacements.items():
        cleaned = cleaned.replace(old, new)
    rendered = mathify_general_text(cleaned)
    for old, new in {
        "{−1, 1}": math_inline(r"\{-1,1\}"),
        "{0, 1}": math_inline(r"\{0,1\}"),
    }.items():
        rendered = rendered.replace(old, new)
    return rendered


def chapter_04_p(text: str) -> str:
    return f"<p>{chapter_04_text_html(text)}</p>"


def chapter_05_code(text: str) -> str:
    return f"<code>{html.escape(text)}</code>"


def chapter_05_text_html(text: str) -> str:
    cleaned = text.strip()
    replacements = {
        "logprices": "log-prices",
        "Int[d]": "int[d]",
        "over-differentiated": "overdifferentiated",
    }
    for old, new in replacements.items():
        cleaned = cleaned.replace(old, new)
    return mathify_general_text(cleaned)


def chapter_05_p(text: str) -> str:
    return f"<p>{chapter_05_text_html(text)}</p>"


def chapter_05_paragraph_html(text: str) -> str | None:
    stripped = text.strip()
    suppress_exact = {
        "n",
        "k",
        "k=0 k k=0 k!",
        "i=0",
        "2! 3!",
        "k=0",
        "with weights 𝜔 { }",
        ",. . . 2! 3! i=0 k!",
        "and values X",
        "[0,1], in 0.1 increments.",
        "[1,2], in 0.1 increments.",
        "(a)",
        "(b)",
        "ling for weight loss with an expanding window (bottom plot)",
        "0 if k > l∗",
        "adfStat (right) corr",
    }
    if stripped in suppress_exact:
        return ""
    suppress_prefixes = (
        "that point is cancelled",
        "that for k > d",
        "quently, the weights converge",
        "consequently, the weights converge",
        "makes the initial weights",
        "(converges to zero from the left)",
        "zero from the right)",
        "k=0 xy = k=0",
        "l, we can determine",
        "𝜏 ∈ [0, 1]",
        "for the weight loss",
        "and X̃ t = lk=0",
        "expanding window’s added weights",
    )
    if stripped.startswith(suppress_prefixes):
        return ""
    if "quently, the weights converge" in stripped:
        return ""
    if stripped.startswith("It is common in finance to find non-stationary"):
        return chapter_05_p(stripped)
    if stripped.startswith("Consider the backshift operator"):
        return (
            "<p>Consider the backshift operator, "
            + math_inline("B")
            + ", applied to a matrix of real-valued features "
            + math_inline(r"\{X_t\}")
            + ", where "
            + math_inline(r"B^kX_t=X_{t-k}")
            + " for any integer "
            + math_inline(r"k\ge0")
            + ". For example, "
            + math_inline(r"(1-B)^2=1-2B+B^2")
            + ", where "
            + math_inline(r"B^2X_t=X_{t-2}")
            + ", so that</p>"
            + math_display(r"(1-B)^2X_t=X_t-2X_{t-1}+X_{t-2}")
            + "<p>Note that, for a positive integer "
            + math_inline("n")
            + ",</p>"
            + math_display(r"(x+y)^n=\sum_{k=0}^{n}\binom{n}{k}x^k y^{n-k}=\sum_{k=0}^{n}\binom{n}{k}x^{n-k}y^k")
            + "<p>For a real number "
            + math_inline("d")
            + ", the binomial series is</p>"
            + math_display(r"(1+x)^d=\sum_{k=0}^{\infty}\binom{d}{k}x^k")
            + "<p>In a fractional model, the exponent "
            + math_inline("d")
            + " is allowed to be a real number, with the following formal binomial series expansion:</p>"
            + math_display(
                r"\begin{aligned}"
                r"(1-B)^d"
                r"&=\sum_{k=0}^{\infty}\binom{d}{k}(-B)^k\\"
                r"&=\sum_{k=0}^{\infty}\frac{\prod_{i=0}^{k-1}(d-i)}{k!}(-B)^k\\"
                r"&=\sum_{k=0}^{\infty}\left(\prod_{i=0}^{k-1}\frac{d-i}{k-i}\right)(-B)^k\\"
                r"&=1-dB+\frac{d(d-1)}{2!}B^2-\frac{d(d-1)(d-2)}{3!}B^3+\cdots"
                r"\end{aligned}"
            )
        )
    if stripped.startswith("Let us see how a real"):
        return (
            "<p>Let us see how a real (non-integer) positive "
            + math_inline("d")
            + " preserves memory. This arithmetic series consists of a dot product</p>"
            + math_display(r"\widetilde X_t=\sum_{k=0}^{\infty}\omega_k X_{t-k}")
            + "<p>with weights</p>"
            + math_display(
                r"\omega=\left\{1,-d,\frac{d(d-1)}{2!},-\frac{d(d-1)(d-2)}{3!},\ldots,"
                r"(-1)^k\frac{\prod_{i=0}^{k-1}(d-i)}{k!},\ldots\right\}"
            )
            + "<p>and values</p>"
            + math_display(r"X=\{X_t,X_{t-1},X_{t-2},X_{t-3},\ldots,X_{t-k},\ldots\}")
        )
    if stripped.startswith("When d is a positive integer"):
        return (
            "<p>When "
            + math_inline("d")
            + " is a positive integer number,</p>"
            + math_display(r"\frac{\prod_{i=0}^{k-1}(d-i)}{k!}=0,\quad \forall k>d")
            + "<p>and memory beyond that point is cancelled. For example, "
            + math_inline("d=1")
            + " is used to compute returns, where "
            + math_inline(r"\frac{\prod_{i=0}^{k-1}(d-i)}{k!}=0,\ \forall k>1")
            + ", and "
            + math_inline(r"\omega=\{1,-1,0,0,\ldots\}")
            + ".</p>"
        )
    if stripped.startswith("Looking at the sequence of weights"):
        return (
            "<p>Looking at the sequence of weights, "
            + math_inline(r"\omega")
            + ", we can appreciate that for "
            + math_inline(r"k=0,\ldots,\infty")
            + ", with "
            + math_inline(r"\omega_0=1")
            + ", the weights can be generated iteratively as:</p>"
            + math_display(r"\omega_k=-\omega_{k-1}\frac{d-k+1}{k}")
        )
    if stripped.startswith("Figure 5.1 plots the sequence"):
        return (
            "<p>Figure 5.1 plots the sequence of weights used to compute each value of the fractionally differentiated series. The legend reports the value of "
            + math_inline("d")
            + " used to generate each sequence, the x-axis indicates the value of "
            + math_inline("k")
            + ", and the y-axis shows the value of "
            + math_inline(r"\omega_k")
            + ". For example, for "
            + math_inline("d=0")
            + ", all weights are 0 except for "
            + math_inline(r"\omega_0=1")
            + ". That is the case where the differentiated series coincides with the original one. For "
            + math_inline("d=1")
            + ", all weights are 0 except for "
            + math_inline(r"\omega_0=1")
            + " and "
            + math_inline(r"\omega_1=-1")
            + ". That is the standard first-order integer differentiation, which is used to derive log-price returns. Anywhere in between these two cases, all weights after "
            + math_inline(r"\omega_0=1")
            + " are negative and greater than "
            + math_inline("-1")
            + ".</p>"
            "<p>Figure 5.2 plots the sequence of weights where "
            + math_inline(r"d\in[1,2]")
            + ", at increments of 0.1. For "
            + math_inline("d>1")
            + ", we observe "
            + math_inline(r"\omega_1<-1")
            + " and "
            + math_inline(r"\omega_k>0,\ \forall k\ge2")
            + ". Snippet 5.1 lists the code used to generate these plots.</p>"
        )
    if stripped.startswith("Let us consider the convergence"):
        return (
            "<p>Let us consider the convergence of the weights. From the above result, we can see that for "
            + math_inline("k>d")
            + ", if "
            + math_inline(r"\omega_{k-1}\ne0")
            + ", then "
            + math_inline(r"\left|\frac{\omega_k}{\omega_{k-1}}\right|=\left|\frac{d-k+1}{k}\right|<1")
            + ", and "
            + math_inline(r"\omega_k=0")
            + " otherwise. Consequently, the weights converge asymptotically to zero, as an infinite product of factors within the unit circle. Also, for a positive "
            + math_inline("d")
            + " and "
            + math_inline("k<d+1")
            + ", we have "
            + math_inline(r"\frac{d-k+1}{k}\ge0")
            + ", which makes the initial weights alternate in sign.</p>"
            "<p>For a non-integer "
            + math_inline("d")
            + ", once "
            + math_inline(r"k\ge d+1")
            + ", "
            + math_inline(r"\omega_k")
            + " will be negative if "
            + math_inline(r"\operatorname{int}[d]")
            + " is even, and positive otherwise. Summarizing, "
            + math_inline(r"\lim_{k\to\infty}\omega_k=0^-")
            + " when "
            + math_inline(r"\operatorname{int}[d]")
            + " is even, and "
            + math_inline(r"\lim_{k\to\infty}\omega_k=0^+")
            + " when "
            + math_inline(r"\operatorname{int}[d]")
            + " is odd. In the special case "
            + math_inline(r"d\in(0,1)")
            + ", this means that "
            + math_inline(r"-1<\omega_k<0,\ \forall k>0")
            + ". This alternation of weight signs is necessary to make "
            + math_inline(r"\{\widetilde X_t\}_{t=1,\ldots,T}")
            + " stationary, as memory wanes or is offset over the long run.</p>"
        )
    if stripped.startswith("Let us discuss how to fractionally differentiate"):
        return (
            "<p>Let us discuss how to fractionally differentiate a finite time series in practice. Suppose a time series with "
            + math_inline("T")
            + " real observations, "
            + math_inline(r"\{X_t\}_{t=1,\ldots,T}")
            + ". Because of data limitations, the fractionally differentiated value "
            + math_inline(r"\widetilde X_T")
            + " cannot be computed on an infinite series of weights. For instance, the last point "
            + math_inline(r"\widetilde X_T")
            + " will use weights "
            + math_inline(r"\{\omega_k\}_{k=0,\ldots,T-1}")
            + ", and "
            + math_inline(r"\widetilde X_{T-l}")
            + " will use weights "
            + math_inline(r"\{\omega_k\}_{k=0,\ldots,T-l-1}")
            + ". This means that the initial points will have a different amount of memory compared to the final points.</p>"
            "<p>For each "
            + math_inline("l")
            + ", we can determine the relative weight-loss,</p>"
            + math_display(r"\lambda_l=\frac{\sum_{j=T-l}^{T}|\omega_j|}{\sum_{i=0}^{T-1}|\omega_i|}")
            + "<p>Given a tolerance level "
            + math_inline(r"\tau\in[0,1]")
            + ", we can determine the value "
            + math_inline(r"l^*")
            + " such that "
            + math_inline(r"\lambda_{l^*}\le\tau")
            + " and "
            + math_inline(r"\lambda_{l^*+1}>\tau")
            + ". This value "
            + math_inline(r"l^*")
            + " corresponds to the first results "
            + math_inline(r"\{\widetilde X_t\}_{t=1,\ldots,l^*}")
            + " where the weight-loss is beyond the acceptable threshold, "
            + math_inline(r"\lambda_t>\tau")
            + " (e.g., "
            + math_inline(r"\tau=0.01")
            + "). From our earlier discussion, it is clear that "
            + math_inline(r"\lambda_{l^*}")
            + " depends on the convergence speed of "
            + math_inline(r"\{\omega_k\}")
            + ", which in turn depends on "
            + math_inline(r"d\in[0,1]")
            + ". For "
            + math_inline("d=1")
            + ", "
            + math_inline(r"\omega_k=0,\ \forall k>1")
            + ", and "
            + math_inline(r"\lambda_l=0,\ \forall l>1")
            + ", hence it suffices to drop "
            + math_inline(r"\widetilde X_1")
            + ". As "
            + math_inline(r"d\to0^+")
            + ", "
            + math_inline(r"l^*")
            + " increases, and a larger portion of the initial "
            + math_inline(r"\{\widetilde X_t\}_{t=1,\ldots,l^*}")
            + " needs to be dropped in order to keep the weight-loss "
            + math_inline(r"\lambda_{l^*}\le\tau")
            + ".</p>"
            "<p>Figure 5.3 plots the E-mini S&amp;P 500 futures trade bars of size 1E4, rolled forward, fractionally differentiated, with parameters ("
            + math_inline(r"d=.4,\ \tau=1")
            + ") on the top and parameters ("
            + math_inline(r"d=.4,\ \tau=1E-2")
            + ") on the bottom. The negative drift in both plots is caused by the negative weights that are added to the initial observations as the window is expanded. When we do not control for weight loss, the negative drift is extreme, to the point that only that trend is visible. The negative drift is somewhat more moderate after controlling for the weight loss; however, it is still substantial, because values "
            + math_inline(r"\{\widetilde X_t\}_{t=l^*+1,\ldots,T}")
            + " are computed on an expanding window. This problem can be corrected by a fixed-width window, implemented in Snippet 5.2.</p>"
        )
    if stripped.startswith("Alternatively, fractional differentiation"):
        return (
            "<p>Alternatively, fractional differentiation can be computed using a fixed-width window, that is, dropping the weights after their modulus ("
            + math_inline(r"|\omega_k|")
            + ") falls below a given threshold value ("
            + math_inline(r"\tau")
            + "). This is equivalent to finding the first "
            + math_inline(r"l^*")
            + " such that "
            + math_inline(r"|\omega_{l^*}|\ge\tau")
            + " and "
            + math_inline(r"|\omega_{l^*+1}|\le\tau")
            + ", setting a new variable "
            + math_inline(r"\widetilde\omega_k")
            + ":</p>"
            + math_display(r"\widetilde\omega_k=\begin{cases}\omega_k, & k\le l^*\\0, & k>l^*\end{cases}")
            + "<p>and "
            + math_inline(r"\widetilde X_t=\sum_{k=0}^{l^*}\widetilde\omega_k X_{t-k}")
            + ", for "
            + math_inline(r"t=T-l^*+1,\ldots,T")
            + ". Figure 5.4 plots E-mini S&amp;P 500 futures trade bars of size 1E4, rolled forward, fractionally differentiated ("
            + math_inline(r"d=.4,\ \tau=1E-5")
            + "). This procedure has the advantage that the same vector of weights is used across all estimates of "
            + math_inline(r"\{\widetilde X_t\}_{t=l^*,\ldots,T}")
            + ", hence avoiding the negative drift caused by an expanding window's added weights. The result is a driftless blend of level plus noise, as expected. The distribution is no longer Gaussian, as a result of the skewness and excess kurtosis that comes with memory; however, it is stationary. Snippet 5.3 presents an implementation of this idea.</p>"
        )
    if stripped.startswith("Consider a series {Xt }t=1"):
        return (
            "<p>Consider a series "
            + math_inline(r"\{X_t\}_{t=1,\ldots,T}")
            + ". Applying the fixed-width window fracdiff (FFD) method on this series, we can compute the minimum coefficient "
            + math_inline(r"d^*")
            + " such that the resulting fractionally differentiated series "
            + math_inline(r"\{\widetilde X_t\}_{t=l^*,\ldots,T}")
            + " is stationary. This coefficient "
            + math_inline(r"d^*")
            + " quantifies the amount of memory that needs to be removed to achieve stationarity. If "
            + math_inline(r"\{X_t\}_{t=l^*,\ldots,T}")
            + " is already stationary, then "
            + math_inline(r"d^*=0")
            + ". If "
            + math_inline(r"\{X_t\}_{t=l^*,\ldots,T}")
            + " contains a unit root, then "
            + math_inline(r"d^*<1")
            + ". If "
            + math_inline(r"\{X_t\}_{t=l^*,\ldots,T}")
            + " exhibits explosive behavior (like in a bubble), then "
            + math_inline(r"d^*>1")
            + ". A case of particular interest is "
            + math_inline(r"0<d^*\ll1")
            + ", when the original series is mildly non-stationary. In this case, although differentiation is needed, a full integer differentiation removes excessive memory and predictive power.</p>"
            "<p>Figure 5.5 illustrates this concept. On the right y-axis, it plots the ADF statistic computed on E-mini S&amp;P 500 futures log-prices, rolled forward using the ETF trick.</p>"
        )
    if stripped.startswith("(see Chapter 2), downsampled"):
        return (
            "<p>Following the ETF trick (see Chapter 2), the series is downsampled to daily frequency, going back to the contract's inception. On the x-axis, Figure 5.5 displays the "
            + math_inline("d")
            + " value used to generate the series on which the ADF statistic was computed. The original series has an ADF statistic of -0.3387, while the returns series has an ADF statistic of -46.9114. At a 95% confidence level, the test's critical value is -2.8623. The ADF statistic crosses that threshold in the vicinity of "
            + math_inline("d=0.35")
            + ". The left y-axis plots the correlation between the original series ("
            + math_inline("d=0")
            + ") and the differentiated series at various "
            + math_inline("d")
            + " values. At "
            + math_inline("d=0.35")
            + " the correlation is still very high, at 0.995. This confirms that the procedure introduced in this chapter has been successful in achieving stationarity without giving up too much memory. In contrast, the correlation between the original series and the returns series is only 0.03, hence showing that the standard integer differentiation wipes out the series' memory almost entirely.</p>"
            "<p>Virtually all finance papers attempt to recover stationarity by applying an integer differentiation "
            + math_inline(r"d=1\gg0.35")
            + ", which means that most studies have overdifferentiated the series, that is, they have removed much more memory than was necessary to satisfy standard econometric assumptions. Snippet 5.4 lists the code used to produce these results.</p>"
        )
    if stripped.startswith("The example on E-mini futures"):
        return (
            "<p>The example on E-mini futures is by no means an exception. Table 5.1 shows the ADF statistics after applying "
            + math_inline(r"\operatorname{FFD}(d)")
            + " on various values of "
            + math_inline("d")
            + ", for 87 of the most liquid futures worldwide. In all cases, the standard "
            + math_inline("d=1")
            + " used for computing returns implies overdifferentiation. In fact, in all cases stationarity is achieved with "
            + math_inline("d<0.6")
            + ". In some cases, like orange juice (JO1 Comdty) or live cattle (LC1 Comdty), no differentiation at all was needed.</p>"
        )
    if stripped.startswith("At a 95% confidence level"):
        return (
            "<p>At a 95% confidence level, the ADF test's critical value is -2.8623. All of the log-price series achieve stationarity at "
            + math_inline("d<0.6")
            + ", and the great majority are stationary at "
            + math_inline("d<0.3")
            + ".</p>"
        )
    if "logprices" in stripped or "Int[d]" in stripped or "over-differentiated" in stripped:
        return chapter_05_p(stripped)
    return None


def chapter_06_code(text: str) -> str:
    return f"<code>{html.escape(text)}</code>"


def chapter_06_text_html(text: str) -> str:
    cleaned = text.strip()
    replacements = {
        "unpre- dictable": "unpredictable",
        "discrep- ancy": "discrepancy",
        "con- verges": "converges",
        "boot- strapping": "bootstrapping",
        "weak estima- tors": "weak estimators",
    }
    for old, new in replacements.items():
        cleaned = cleaned.replace(old, new)
    rendered = mathify_general_text(cleaned)
    for token in sorted(
        [
            "BaggingClassifier",
            "DecisionTreeClassifier",
            "RandomForestClassifier",
            "StratifiedKFold(n_splits=k, shuffle=False)",
            "class_weight='balanced_subsample'",
            "max_depth",
            "max_features",
            "max_iter",
            "max_iter=-1",
            "max_samples",
            "max_samples=out['tW'].mean()",
            "min_weight_fraction_leaf",
            "tol",
            "tol=1E-3",
        ],
        key=len,
        reverse=True,
    ):
        rendered = rendered.replace(html.escape(token), chapter_06_code(token))
    return rendered


def chapter_06_p(text: str) -> str:
    return f"<p>{chapter_06_text_html(text)}</p>"


def chapter_06_sup_p(text: str) -> str:
    rendered = chapter_06_text_html(text)
    rendered = re.sub(r"&lt;sup&gt;(\d+)&lt;/sup&gt;", r"<sup>\1</sup>", rendered)
    return f"<p>{rendered}</p>"


def chapter_06_paragraph_html(text: str) -> str | None:
    stripped = text.strip()
    suppress_exact = {
        "in this article useful: https://en.wikipedia.org/wiki/Bias%E2%80%93variance_tradeoff.",
        "represented by 𝜎𝜀2 ). This mean-squared error can be decomposed as",
        "⎛ ⎞",
        "⎜⏟⏞⏞⏞⏞⏞⏞⏟⏞⏞⏞⏞⏞⏞⏟⎟ ⏟⏟⏟ ⏟⏟⏟ ⎝ bias ⎠ variance noise",
        "N N N N",
        "N i=1 i N i=1 j=1 N i=1 j≠i",
        "⎛ ⎞ ⎜ ⎟ ⎜ ⎟",
        "⎟ N ⎜ ⏟ ⏟ ⏟ ⎟ ⎜ ⎟",
        "⎝ for a fixed i ⎠ ( )",
        "N",
        "∑N i",
        "⌊ ⌋ N∕",
        "k k i i=0",
        "the number of estimators (N), and k = 2",
        "science, the problem addressed by this theorem shares similarities with the above discussion.",
        "-forest-many-is-better-than-one/.",
        "what-is-the-difference-between-bagging-and-boosting/.",
    }
    if stripped in suppress_exact:
        return ""
    suppress_prefixes = (
        "1 For an introduction to ensemble methods",
        "and the average correlation among their forecasts",
        "where 𝜎i,j is the covariance",
        "The equation above shows that bagging is only effective",
        "1; as 𝜌̄",
        "The implication is that for a sufficiently large N",
        "(a) clf=RandomForestClassifier",
        "are determined by the accuracy",
    )
    if stripped.startswith(suppress_prefixes):
        if stripped.startswith("1 For an introduction to ensemble methods"):
            return (
                '<p class="footnote"><sup>1</sup> For an introduction to ensemble methods, please visit '
                '<a href="http://scikit-learn.org/stable/modules/ensemble.html">http://scikit-learn.org/stable/modules/ensemble.html</a>.</p>'
                '<p class="footnote"><sup>2</sup> I would not typically cite Wikipedia, however, on this subject the user may find some of the illustrations in this article useful: '
                '<a href="https://en.wikipedia.org/wiki/Bias%E2%80%93variance_tradeoff">https://en.wikipedia.org/wiki/Bias%E2%80%93variance_tradeoff</a>.</p>'
            )
        return ""
    if stripped.startswith("3 For an intuitive explanation of Random Forest"):
        return (
            '<p class="footnote"><sup>3</sup> For an intuitive explanation of Random Forest, visit '
            '<a href="https://quantdare.com/random-forest-many-is-better-than-one/">https://quantdare.com/random-forest-many-is-better-than-one/</a>.</p>'
        )
    if stripped.startswith("4 For a visual explanation of the difference between bagging"):
        return (
            '<p class="footnote"><sup>4</sup> For a visual explanation of the difference between bagging and boosting, visit '
            '<a href="https://quantdare.com/what-is-the-difference-between-bagging-and-boosting/">https://quantdare.com/what-is-the-difference-between-bagging-and-boosting/</a>.</p>'
        )
    if stripped.startswith("In this chapter we will discuss"):
        return chapter_06_sup_p(stripped.replace("methods.1", "methods.<sup>1</sup>"))
    if stripped.startswith("ML models generally suffer"):
        return chapter_06_sup_p(stripped.replace("errors:2", "errors:<sup>2</sup>"))
    if stripped.startswith("Consider a training set of observations"):
        return (
            "<p>Consider a training set of observations "
            + math_inline(r"\{x_i\}_{i=1,\ldots,n}")
            + " and real-valued outcomes "
            + math_inline(r"\{y_i\}_{i=1,\ldots,n}")
            + ". Suppose a function "
            + math_inline("f[x]")
            + " exists, such that "
            + math_inline(r"y=f[x]+\varepsilon")
            + ", where "
            + math_inline(r"\varepsilon")
            + " is white noise with "
            + math_inline(r"\mathbb{E}[\varepsilon_i]=0")
            + " and "
            + math_inline(r"\mathbb{E}[\varepsilon_i^2]=\sigma_\varepsilon^2")
            + ". We would like to estimate the function "
            + math_inline(r"\hat f[x]")
            + " that best fits "
            + math_inline("f[x]")
            + ", in the sense of making the mean squared estimation error "
            + math_inline(r"\mathbb{E}[(y_i-\hat f[x_i])^2]")
            + " minimal. The mean squared error cannot be zero because of the noise represented by "
            + math_inline(r"\sigma_\varepsilon^2")
            + ". This error can be decomposed as</p>"
            + math_display(
                r"\mathbb{E}\left[(y_i-\hat f[x_i])^2\right]"
                r"=\left(\underbrace{\mathbb{E}[\hat f[x_i]-f[x_i]]}_{\text{bias}}\right)^2"
                r"+\underbrace{\mathbb{V}[\hat f[x_i]]}_{\text{variance}}"
                r"+\underbrace{\sigma_\varepsilon^2}_{\text{noise}}"
            )
        )
    if stripped.startswith("Bagging’s main advantage"):
        return (
            "<p>Bagging's main advantage is that it reduces forecasts' variance, hence helping address overfitting. The variance of the bagged prediction "
            + math_inline(r"\varphi_i[c]")
            + " is a function of the number of bagged estimators "
            + math_inline("N")
            + ", the average variance of a single estimator's prediction "
            + math_inline(r"\bar\sigma^2")
            + ", and the average correlation among their forecasts "
            + math_inline(r"\bar\rho")
            + ":</p>"
            + math_display(
                r"\begin{aligned}"
                r"\mathbb{V}\left[\frac{1}{N}\sum_{i=1}^{N}\varphi_i[c]\right]"
                r"&=\frac{1}{N^2}\sum_{i=1}^{N}\sum_{j=1}^{N}\sigma_{i,j}\\"
                r"&=\frac{1}{N^2}\sum_{i=1}^{N}\left(\sigma_i^2+\sum_{j\ne i}^{N}\sigma_i\sigma_j\rho_{i,j}\right)\\"
                r"&=\frac{\bar\sigma^2+(N-1)\bar\sigma^2\bar\rho}{N}\\"
                r"&=\bar\sigma^2\left(\bar\rho+\frac{1-\bar\rho}{N}\right)."
                r"\end{aligned}"
            )
            + "<p>Here "
            + math_inline(r"\sigma_{i,j}")
            + " is the covariance of predictions by estimators "
            + math_inline("i,j")
            + ". The average variance and average correlation are defined by</p>"
            + math_display(
                r"\bar\sigma^2=\frac{1}{N}\sum_{i=1}^{N}\sigma_i^2,\qquad"
                r"\bar\rho=\frac{1}{\bar\sigma^2N(N-1)}\sum_{i=1}^{N}\sum_{j\ne i}^{N}\sigma_i\sigma_j\rho_{i,j}."
            )
            + "<p>The equation above shows that bagging is only effective to the extent that "
            + math_inline(r"\bar\rho<1")
            + "; as "
            + math_inline(r"\bar\rho\to1")
            + ", "
            + math_inline(r"\mathbb{V}\left[N^{-1}\sum_{i=1}^{N}\varphi_i[c]\right]\to\bar\sigma^2")
            + ". One of the goals of sequential bootstrapping (Chapter 4) is to produce samples as independent as possible, thereby reducing "
            + math_inline(r"\bar\rho")
            + ", which should lower the variance of bagging classifiers. Figure 6.1 plots the standard deviation of the bagged prediction as a function of "
            + math_inline(r"N\in[5,30]")
            + ", "
            + math_inline(r"\bar\rho\in[0,1]")
            + ", and "
            + math_inline(r"\bar\sigma=1")
            + ".</p>"
        )
    if stripped.startswith("Consider a bagging classifier"):
        return (
            "<p>Consider a bagging classifier that makes a prediction on "
            + math_inline("k")
            + " classes by majority voting among "
            + math_inline("N")
            + " independent classifiers. We can label the predictions as "
            + math_inline(r"\{0,1\}")
            + ", where "
            + math_inline("1")
            + " means a correct prediction. The accuracy of a classifier is the probability "
            + math_inline("p")
            + " of labeling a prediction as "
            + math_inline("1")
            + ". On average we will get "
            + math_inline("Np")
            + " predictions labeled as "
            + math_inline("1")
            + ", with variance "
            + math_inline(r"Np(1-p)")
            + ". Majority voting makes the correct prediction when the most forecasted class is observed. For example, for "
            + math_inline("N=10")
            + " and "
            + math_inline("k=3")
            + ", the bagging classifier made a correct prediction when class "
            + math_inline("A")
            + " was observed and the cast votes were "
            + math_inline(r"[A,B,C]=[4,3,3]")
            + ". However, it made an incorrect prediction when class "
            + math_inline("A")
            + " was observed and the cast votes were "
            + math_inline(r"[A,B,C]=[4,1,5]")
            + ". A sufficient condition is that the sum of these labels is "
            + math_inline(r"X>\frac{N}{2}")
            + ". A necessary, non-sufficient condition is that "
            + math_inline(r"X>\frac{N}{k}")
            + ", which occurs with probability</p>"
            + math_display(
                r"P\left[X>\frac{N}{k}\right]"
                r"=1-P\left[X\le\frac{N}{k}\right]"
                r"=1-\sum_{i=0}^{\lfloor N/k\rfloor}\binom{N}{i}p^i(1-p)^{N-i}."
            )
            + "<p>The implication is that for a sufficiently large "
            + math_inline("N")
            + ", say "
            + math_inline(r"N>p(p-1/k)^{-2}")
            + ", then "
            + math_inline(r"p>\frac{1}{k}\Rightarrow P\left[X>\frac{N}{k}\right]>p")
            + ", hence the bagging classifier's accuracy exceeds the average accuracy of the individual classifiers. Snippet 6.1 implements this calculation.</p>"
        )
    if stripped.startswith("This is a strong argument"):
        return (
            "<p>This is a strong argument in favor of bagging any classifier in general, when computational requirements permit it. However, unlike boosting, bagging cannot improve the accuracy of poor classifiers: If the individual learners are poor classifiers ("
            + math_inline(r"p\ll\frac{1}{k}")
            + "), majority voting will still perform poorly, although with lower variance. Figure 6.2 illustrates these facts. Because it is easier to achieve "
            + math_inline(r"\bar\rho\ll1")
            + " than "
            + math_inline(r"p>\frac{1}{k}")
            + ", bagging is more likely to be successful in reducing variance than in reducing bias.</p>"
            "<p>For further analysis on this topic, the reader is directed to Condorcet's Jury Theorem. Although the theorem is derived for the purposes of majority voting in political science, the problem addressed by this theorem shares similarities with the above discussion.</p>"
        )
    if stripped.startswith("In Chapter 4 we studied one reason"):
        return (
            "<p>In Chapter 4 we studied one reason why financial observations cannot be assumed to be IID. Redundant observations have two detrimental effects on bagging. First, the samples drawn with replacement are more likely to be virtually identical, even if they do not share the same observations. This makes "
            + math_inline(r"\bar\rho\approx1")
            + ", and bagging will not reduce variance, regardless of "
            + math_inline("N")
            + ". For example, if each observation at "
            + math_inline("t")
            + " is labeled according to the return between "
            + math_inline("t")
            + " and "
            + math_inline("t+100")
            + ", we should sample 1% of the observations per bagged estimator, but not more. Chapter 4, Section 4.5 recommended three alternative solutions, one of which consisted of setting "
            + chapter_06_code("max_samples=out['tW'].mean()")
            + " in sklearn's implementation of the bagging classifier class. Another, better solution was to apply the sequential bootstrap method.</p>"
            "<p>The second detrimental effect from observation redundancy is that out-of-bag accuracy will be inflated. This happens because random sampling with replacement places in the training set samples that are very similar to those out-of-bag. In such a case, a proper stratified k-fold cross-validation without shuffling before partitioning will show a much lower testing-set accuracy than the one estimated out-of-bag. For this reason, it is advisable to set "
            + chapter_06_code("StratifiedKFold(n_splits=k, shuffle=False)")
            + " when using that sklearn class, cross-validate the bagging classifier, and ignore the out-of-bag accuracy results. A low number "
            + math_inline("k")
            + " is preferred to a high one, as excessive partitioning would again place in the testing set samples too similar to those used in the training set.</p>"
        )
    if stripped.startswith("one, as excessive partitioning"):
        return ""
    if stripped.startswith("Decision trees are known to be prone"):
        return (
            "<p>Decision trees are known to be prone to overfitting, which increases the variance of the forecasts.<sup>3</sup> In order to address this concern, the random forest (RF) method was designed to produce ensemble forecasts with lower variance.</p>"
            "<p>RF shares some similarities with bagging, in the sense of training independent individual estimators over bootstrapped subsets of the data. The key difference with bagging is that random forests incorporate a second level of randomness: When optimizing each node split, only a random subsample, without replacement, of the attributes will be evaluated, with the purpose of further decorrelating the estimators.</p>"
            "<p>Like bagging, RF reduces forecasts' variance without overfitting, as long as "
            + math_inline(r"\bar\rho<1")
            + ". A second advantage is that RF evaluates feature importance, which we will discuss in depth in Chapter 8. A third advantage is that RF provides out-of-bag accuracy estimates, although in financial applications they are likely to be inflated, as discussed in Section 6.3.3. But like bagging, RF will not necessarily exhibit lower bias than individual decision trees.</p>"
            "<p>If a large number of samples are redundant, or non-IID, overfitting will still take place: Sampling randomly with replacement will build a large number of essentially identical trees ("
            + math_inline(r"\bar\rho\approx1")
            + "), where each decision tree is overfit, a flaw for which decision trees are notorious. Unlike bagging, RF always fixes the size of the bootstrapped samples to match the size of the training dataset. Let us review ways we can address this RF overfitting problem in sklearn. For illustration purposes, I will refer to sklearn's classes; however, these solutions can be applied to any implementation:</p>"
        )
    if stripped.startswith("In summary, Snippet 6.2"):
        return chapter_06_p(stripped)
    if stripped.startswith("When fitting decision trees"):
        return (
            "<p>When fitting decision trees, a rotation of the feature space in a direction that aligns with the axes typically reduces the number of levels needed by the tree. For this reason, I suggest you fit RF on a PCA of the features, as that may speed up calculations and reduce some overfitting, more on this in Chapter 8. Also, as discussed in Chapter 4, Section 4.8, "
            + chapter_06_code("class_weight='balanced_subsample'")
            + " will help you prevent the trees from misclassifying minority classes.</p>"
        )
    if stripped.startswith("Kearns and Valiant"):
        return (
            "<p>Kearns and Valiant [1989] were among the first to ask whether one could combine weak estimators in order to achieve one with high accuracy. Shortly after, Schapire [1990] demonstrated that the answer to that question was affirmative, using the procedure we today call boosting. In general terms, it works as follows: First, generate one training set by random sampling with replacement, according to some sample weights initialized with uniform weights. Second, fit one estimator using that training set. Third, if the single estimator achieves an accuracy greater than the acceptance threshold, for example 50% in a binary classifier, so that it performs better than chance, the estimator is kept; otherwise, it is discarded. Fourth, give more weight to misclassified observations, and less weight to correctly classified observations. Fifth, repeat the previous steps until "
            + math_inline("N")
            + " estimators are produced. Sixth, the ensemble forecast is the weighted average of the individual forecasts from the "
            + math_inline("N")
            + " models, where the weights are determined by the accuracy of the individual estimators. There are many boosting algorithms, of which AdaBoost is one of the most popular (Geron [2017]). Figure 6.3 summarizes the decision flow of a standard AdaBoost implementation.</p>"
        )
    if stripped.startswith("From the above description"):
        return chapter_06_sup_p(stripped.replace("bagging:4", "bagging:<sup>4</sup>"))
    if stripped.startswith("As you know, several popular ML algorithms"):
        return (
            "<p>As you know, several popular ML algorithms do not scale well with the sample size. Support vector machines (SVMs) are a prime example. If you attempt to fit an SVM on a million observations, it may take a while until the algorithm converges. And even once it has converged, there is no guarantee that the solution is a global optimum, or that it is not overfit.</p>"
            "<p>One practical approach is to build a bagging algorithm, where the base estimator belongs to a class that does not scale well with the sample size, like SVM. When defining that base estimator, we will impose a tight early stopping condition. For example, in sklearn's SVM implementation, you could set a low value for the "
            + chapter_06_code("max_iter")
            + " parameter, say 1E5 iterations. The default value is "
            + chapter_06_code("max_iter=-1")
            + ", which tells the estimator to continue performing iterations until errors fall below a tolerance level. Alternatively, you could raise the tolerance level through the parameter "
            + chapter_06_code("tol")
            + ", which has a default value "
            + chapter_06_code("tol=1E-3")
            + ". Either of these two parameters will force an early stop. You can stop other algorithms early with equivalent parameters, like the number of levels in an RF ("
            + chapter_06_code("max_depth")
            + "), or the minimum weighted fraction of the sum total of weights, of all the input samples, required to be at a leaf node ("
            + chapter_06_code("min_weight_fraction_leaf")
            + ").</p>"
            "<p>Given that bagging algorithms can be parallelized, we are transforming a large sequential task into many smaller ones that are run simultaneously. Of course, the early stopping will increase the variance of the outputs from the individual base estimators; however, that increase can be more than offset by the variance reduction associated with the bagging algorithm. You can control that reduction by adding more independent base estimators. Used in this way, bagging will allow you to achieve fast and robust estimates on extremely large datasets.</p>"
        )
    return None


def chapter_07_code(text: str) -> str:
    return f"<code>{html.escape(text)}</code>"


def chapter_07_text_html(text: str) -> str:
    cleaned = text.strip()
    replacements = {
        "kfold CV": "k-fold CV",
        "kx1": "k x 1",
        "hyperparameter": "hyper-parameter",
        "informa- tion": "information",
        "scikit- learn": "scikit-learn",
        "Snip- pet": "Snippet",
    }
    for old, new in replacements.items():
        cleaned = cleaned.replace(old, new)
    rendered = mathify_general_text(cleaned)
    for token in sorted(
        [
            "BaggingClassifier",
            "KFold",
            "PurgedKFold",
            "classes_",
            "cross_val_score",
            "cvScore",
            "getTrainTimes",
            "log_loss",
            "max_samples",
            "numpy",
            "pandas",
            "sample_weight",
            "testTimes",
        ],
        key=len,
        reverse=True,
    ):
        rendered = rendered.replace(html.escape(token), chapter_07_code(token))
    return rendered


def chapter_07_p(text: str) -> str:
    return f"<p>{chapter_07_text_html(text)}</p>"


def chapter_07_paragraph_html(text: str) -> str | None:
    stripped = text.strip()
    suppress_exact = {
        "A SOLUTION: PURGED K-FOLD CV 105",
        "A SOLUTION: PURGED K-FOLD CV 107",
        "(a) The ML algorithm is trained on all subsets excluding i. (b) The fitted ML algorithm is tested on i.",
        "k∗ , performance will not improve, indicating that the backtest is not profiting from leaks. Figure 7.2 plots one partition of the k-fold CV. The test set is surrounded by two train sets, generating two overlaps that must be purged to prevent leakage.",
        "particular context of model development. In general, we need to purge and embargo overlapping training observations whenever we produce a train/test split, whether it is for hyper-parameter fitting, backtesting, or performance evaluation. Snippet 7.3 extends scikit-learn’s KFold class to account for the possibility of leakages of testing information into the training set.",
    }
    if stripped in suppress_exact:
        return ""
    if stripped.startswith("One of the purposes of ML is"):
        return (
            "<p>One of the purposes of ML is to learn the general structure of the data, so that we can produce predictions on future, unseen features. When we test an ML algorithm on the same dataset as was used for training, not surprisingly, we achieve spectacular results. When ML algorithms are misused that way, they are no different from lossy file-compression algorithms: They can summarize the data with extreme fidelity, yet with zero forecasting power.</p>"
            "<p>CV splits observations drawn from an IID process into two sets: the training set and the testing set. Each observation in the complete dataset belongs to one, and only one, set. This is done to prevent leakage from one set into the other, since that would defeat the purpose of testing on unseen data. Further details can be found in the books and articles listed in the references section.</p>"
            "<p>There are many alternative CV schemes, of which one of the most popular is "
            + math_inline("k")
            + "-fold CV. Figure 7.1 illustrates the "
            + math_inline("k")
            + " train/test splits carried out by a "
            + math_inline("k")
            + "-fold CV, where "
            + math_inline("k=5")
            + ". In this scheme:</p>"
        )
    if stripped.startswith("The outcome from k-fold CV"):
        return (
            "<p>The outcome from "
            + math_inline("k")
            + "-fold CV is a "
            + math_inline(r"k\times1")
            + " array of cross-validated performance metrics. For example, in a binary classifier, the model is deemed to have learned something if the cross-validated accuracy is over "
            + math_inline(r"\frac{1}{2}")
            + ", since that is the accuracy we would achieve by tossing a fair coin.</p>"
            "<p>In finance, CV is typically used in two settings: model development, like hyper-parameter tuning, and backtesting. Backtesting is a complex subject that we will discuss thoroughly in Chapters 10-16. In this chapter, we will focus on CV for model development.</p>"
        )
    if stripped.startswith("By now you may have read"):
        return (
            "<p>By now you may have read quite a few papers in finance that present "
            + math_inline("k")
            + "-fold CV evidence that an ML algorithm performs well. Unfortunately, it is almost certain that those results are wrong. One reason "
            + math_inline("k")
            + "-fold CV fails in finance is because observations cannot be assumed to be drawn from an IID process. A second reason for CV's failure is that the testing set is used multiple times in the process of developing a model, leading to multiple testing and selection bias. We will revisit this second cause of failure in Chapters 11-13. For the time being, let us concern ourselves exclusively with the first cause of failure.</p>"
            "<p>Leakage takes place when the training set contains information that also appears in the testing set. Consider a serially correlated feature "
            + math_inline("X")
            + " that is associated with labels "
            + math_inline("Y")
            + " that are formed on overlapping data:</p>"
        )
    if stripped.startswith("By placing t and t + 1"):
        return (
            "<p>By placing "
            + math_inline("t")
            + " and "
            + math_inline("t+1")
            + " in different sets, information is leaked. When a classifier is first trained on "
            + math_inline(r"(X_t,Y_t)")
            + ", and then it is asked to predict "
            + math_inline(r"\mathbb{E}[Y_{t+1}\mid X_{t+1}]")
            + " based on an observed "
            + math_inline(r"X_{t+1}")
            + ", this classifier is more likely to achieve "
            + math_inline(r"Y_{t+1}=\mathbb{E}[Y_{t+1}\mid X_{t+1}]")
            + " even if "
            + math_inline("X")
            + " is an irrelevant feature.</p>"
            "<p>If "
            + math_inline("X")
            + " is a predictive feature, leakage will enhance the performance of an already valuable strategy. The problem is leakage in the presence of irrelevant features, as this leads to false discoveries. There are at least two ways to reduce the likelihood of leakage:</p>"
        )
    if stripped.startswith("Consider the case where Xi and Xj"):
        return (
            "<p>Consider the case where "
            + math_inline("X_i")
            + " and "
            + math_inline("X_j")
            + " are formed on overlapping information, where "
            + math_inline("i")
            + " belongs to the training set and "
            + math_inline("j")
            + " belongs to the testing set. Is this a case of informational leakage? Not necessarily, as long as "
            + math_inline("Y_i")
            + " and "
            + math_inline("Y_j")
            + " are independent. For leakage to take place, it must occur that "
            + math_inline(r"(X_i,Y_i)\approx(X_j,Y_j)")
            + ", and it does not suffice that "
            + math_inline(r"X_i\approx X_j")
            + " or even "
            + math_inline(r"Y_i\approx Y_j")
            + ".</p>"
        )
    if stripped.startswith("Suppose a testing observation"):
        return (
            "<p>Suppose a testing observation whose label "
            + math_inline("Y_j")
            + " is decided based on the information set "
            + math_inline(r"\Phi_j")
            + ". In order to prevent the type of leakage described in the previous section, we would like to purge from the training set any observation whose label "
            + math_inline("Y_i")
            + " is decided based on the information set "
            + math_inline(r"\Phi_i")
            + ", such that "
            + math_inline(r"\Phi_i\cap\Phi_j\ne\emptyset")
            + ".</p>"
        )
    if stripped.startswith("like to purge from the training set") or stripped.startswith("In particular, we will determine"):
        return (
            "<p>In particular, we will determine that there is informational overlap between two observations "
            + math_inline("i")
            + " and "
            + math_inline("j")
            + " whenever "
            + math_inline("Y_i")
            + " and "
            + math_inline("Y_j")
            + " are concurrent (see Chapter 4, Section 4.3), in the sense that both labels are contingent on at least one common random draw. For example, consider a label "
            + math_inline("Y_j")
            + " that is a function of observations in the closed range "
            + math_inline(r"t\in[t_{j,0},t_{j,1}]")
            + ", "
            + math_inline(r"Y_j=f[[t_{j,0},t_{j,1}]]")
            + " (with some abuse of notation). In the context of the triple-barrier labeling method (Chapter 3), it means that the label is the sign of the return spanning between price bars with indices "
            + math_inline(r"t_{j,0}")
            + " and "
            + math_inline(r"t_{j,1}")
            + ", that is "
            + math_inline(r"\operatorname{sgn}[r_{t_{j,0},t_{j,1}}]")
            + ". A label "
            + math_inline(r"Y_i=f[[t_{i,0},t_{i,1}]]")
            + " overlaps with "
            + math_inline("Y_j")
            + " if any of the three sufficient conditions is met:</p>"
        )
    if stripped.startswith("Snippet 7.1 implements this purging"):
        return (
            "<p>Snippet 7.1 implements this purging of observations from the training set. If the testing set is contiguous, in the sense that no training observations occur between the first and last testing observation, then purging can be accelerated: The object "
            + chapter_07_code("testTimes")
            + " can be a pandas series with a single item, spanning the entire testing set.</p>"
        )
    if stripped.startswith("When leakage takes place"):
        return (
            "<p>When leakage takes place, performance improves merely by increasing "
            + math_inline(r"k\to T")
            + ", where "
            + math_inline("T")
            + " is the number of bars. The reason is that the larger the number of testing splits, the greater the number of overlapping observations in the training set. In many cases, purging suffices to prevent leakage: Performance will improve as we increase "
            + math_inline("k")
            + ", because we allow the model to recalibrate more often. But beyond a certain value "
            + math_inline("k^*")
            + ", performance will not improve, indicating that the backtest is not profiting from leaks. Figure 7.2 plots one partition of the "
            + math_inline("k")
            + "-fold CV. The test set is surrounded by two train sets, generating two overlaps that must be purged to prevent leakage.</p>"
        )
    if stripped.startswith("For those cases where purging"):
        return (
            "<p>For those cases where purging is not able to prevent all leakage, we can impose an embargo on training observations after every test set. The embargo does not need to affect training observations prior to a test set, because training labels "
            + math_inline(r"Y_i=f[[t_{i,0},t_{i,1}]]")
            + ", where "
            + math_inline(r"t_{i,1}<t_{j,0}")
            + " (training ends before testing begins), contain information that was available at the testing time "
            + math_inline(r"t_{j,0}")
            + ". In other words, we are only concerned with training labels "
            + math_inline(r"Y_i=f[[t_{i,0},t_{i,1}]]")
            + " that take place immediately after the test, "
            + math_inline(r"t_{j,1}\le t_{i,0}\le t_{j,1}+h")
            + ". We can implement this embargo period "
            + math_inline("h")
            + " by setting "
            + math_inline(r"Y_j=f[[t_{j,0},t_{j,1}+h]]")
            + " before purging. A small value "
            + math_inline(r"h\approx.01T")
            + " often suffices to prevent all leakage, as can be confirmed by testing that performance does not improve indefinitely by increasing "
            + math_inline(r"k\to T")
            + ". Figure 7.3 illustrates the embargoing of train observations immediately after the testing set. Snippet 7.2 implements the embargo logic.</p>"
        )
    if stripped.startswith("In the previous sections we have discussed"):
        return (
            "<p>In the previous sections we have discussed how to produce training/testing splits when labels overlap. That introduced the notion of purging and embargoing, in the particular context of model development. In general, we need to purge and embargo overlapping training observations whenever we produce a train/test split, whether it is for hyper-parameter fitting, backtesting, or performance evaluation. Snippet 7.3 extends scikit-learn's "
            + chapter_07_code("KFold")
            + " class to account for the possibility of leakages of testing information into the training set.</p>"
        )
    if stripped.startswith("that you can verify everything"):
        return ""
    if stripped.startswith("You would think that something as critical"):
        return (
            "<p>You would think that something as critical as cross-validation would be perfectly implemented in one of the most popular ML libraries. Unfortunately that is not the case, and this is one of the reasons you must always read all the code you run, and a strong point in favor of open source. One of the many upsides of open-source code is that you can verify everything and adjust it to your needs. Snippet 7.4 addresses two known sklearn bugs:</p>"
        )
    if stripped.startswith("Please understand that it may take"):
        return (
            "<p>Please understand that it may take a long time until a fix for these bugs is agreed upon, implemented, tested, and released. Until then, you should use "
            + chapter_07_code("cvScore")
            + " in Snippet 7.4, and avoid running the function "
            + chapter_07_code("cross_val_score")
            + ".</p>"
        )
    return None


def chapter_08_code(text: str) -> str:
    return f"<code>{html.escape(text)}</code>"


def chapter_08_text_html(text: str) -> str:
    cleaned = text.strip()
    replacements = {
        "out-ofsample": "out-of-sample",
        "pre- dictor": "predictor",
        "func- tions": "functions",
        "pres- ence": "presence",
        "con- siders": "considers",
        "unimpor- tant": "unimportant",
        "perfor- mance": "performance",
        "correspondance": "correspondence",
        "engenvector": "eigenvector",
        "most importance features": "most important features",
        "scikitlearn.org": "scikit-learn.org",
        "Scipy": "SciPy",
        "weightedtau": "weightedtau",
        "10 ×": "10x",
    }
    for old, new in replacements.items():
        cleaned = cleaned.replace(old, new)
    rendered = mathify_general_text(cleaned)
    for token in sorted(
        [
            "BaggingClassifier",
            "DecisionTreeClassifier",
            "PurgedKFold",
            "RandomForest",
            "RandomForest class",
            "accuracy",
            "featImpMDI",
            "featImpMDA",
            "featImportance",
            "getTestData",
            "log_loss",
            "make_classification",
            "max_features=int(1)",
            "np.nan",
            "plotFeatImportance",
            "scikit-learn",
            "sklearn",
        ],
        key=len,
        reverse=True,
    ):
        rendered = rendered.replace(html.escape(token), chapter_08_code(token))
    return rendered


def chapter_08_p(text: str) -> str:
    return f"<p>{chapter_08_text_html(text)}</p>"


def chapter_08_paragraph_html(text: str) -> str | None:
    stripped = text.strip()
    if stripped in {
        "imp=pd.concat({'mean':df0.mean(),'std':df0.std()*df0.shape[0]**-.5},axis=1) imp/=imp['mean'].sum() return imp",
        "return",
        "1 http://blog.datadive.net/selecting-good-features-part-iii-random-forests/.",
        "columns of X with highest variance, and we would not learn much about the structure or relationship between the variables. Snippet 8.5 computes the smallest number of orthogonal features that explain at least 95% of the variance of Z.",
        "memory and resources, however that is where a sound knowledge of HPC techniques will come in handy (Chapters 20–22).",
        "a function that can carry out each analysis on the same dataset. Snippet 8.8 accom- plishes that, using bagged decision trees as default classifier (Chapter 6).",
    }:
        return ""
    if stripped.startswith("A striking facet of the financial industry"):
        return (
            "<p>A striking facet of the financial industry is that so many very seasoned portfolio managers (including many with a quantitative background) do not realize how easy it is to overfit a backtest. How to backtest properly is not the subject of this chapter; we will address that extremely important topic in Chapters 11-15. The goal of this chapter is to explain one of the analyses that must be performed before any backtest is carried out.</p>"
            "<p>Suppose that you are given a pair of matrices "
            + math_inline(r"(X,y)")
            + ", that respectively contain features and labels for a particular financial instrument. We can fit a classifier on "
            + math_inline(r"(X,y)")
            + " and evaluate the generalization error through a purged "
            + math_inline("k")
            + "-fold cross-validation (CV), as we saw in Chapter 7. Suppose that we achieve good performance. The next natural question is to try to understand what features contributed to that performance. Maybe we could add some features that strengthen the signal responsible for the classifier's predictive power. Maybe we could eliminate some of the features that are only adding noise to the system.</p>"
        )
    if stripped.startswith("natural question is to try"):
        return (
            "<p>Notably, understanding feature importance opens up the proverbial black box. We can gain insight into the patterns identified by the classifier if we understand what source of information is indispensable to it. This is one of the reasons why the black box mantra is somewhat overplayed by the ML skeptics. Yes, the algorithm has learned without us directing the process (that is the whole point of ML!) in a black box, but that does not mean that we cannot (or should not) take a look at what the algorithm has found.</p>"
            "<p>Once we have found what features are important, we can learn more by conducting a number of experiments. Are these features important all the time, or only in some specific environments? What triggers a change in importance over time? Can those regime switches be predicted? Are those important features also relevant to other related financial instruments? Are they relevant to other asset classes? What are the most relevant features across all financial instruments? What is the subset of features with the highest rank correlation across the entire investment universe? This is a much better way of researching strategies than the foolish backtest cycle. Let me state this maxim as one of the most critical lessons I hope you learn from this book:</p>"
        )
    if stripped.startswith("Sklearn’s RandomForest class implements MDI"):
        return (
            "<p>Sklearn's <code>RandomForest</code> class implements MDI as the default feature importance score. This choice is likely motivated by the ability to compute MDI on the fly, with minimum computational cost.<sup>1</sup> Snippet 8.2 illustrates an implementation of MDI, incorporating the considerations listed earlier.</p>"
            '<p class="footnote"><sup>1</sup> <a href="http://blog.datadive.net/selecting-good-features-part-iii-random-forests/">http://blog.datadive.net/selecting-good-features-part-iii-random-forests/</a>.</p>'
        )
    if stripped.startswith("purged k-fold CV"):
        return (
            "<p>Snippet 8.3 implements MDA feature importance with sample weights, with purged "
            + math_inline("k")
            + "-fold CV, and with scoring by negative log-loss or accuracy. It measures MDA importance as a function of the improvement (from permutating to not permutating the feature), relative to the maximum possible score (negative log-loss of 0, or accuracy of 1). Note that, in some cases, the improvement may be negative, meaning that the feature is actually detrimental to the forecasting power of the ML algorithm.</p>"
        )
    if stripped.startswith("Single feature importance"):
        return (
            "<p>Single feature importance (SFI) is a cross-section predictive-importance (out-of-sample) method. It computes the OOS performance score of each feature in isolation. A few considerations:</p>"
        )
    if stripped.startswith("As argued in Section 8.3"):
        return (
            "<p>As argued in Section 8.3, substitution effects dilute the importance of features measured by MDI, and significantly underestimate the importance of features measured by MDA. A partial solution is to orthogonalize the features before applying MDI and MDA. An orthogonalization procedure such as principal components analysis (PCA) does not prevent all substitution effects, but at least it should alleviate the impact of linear substitution effects.</p>"
            "<p>Consider a matrix "
            + math_inline(r"\{X_{t,n}\}")
            + " of stationary features, with observations "
            + math_inline(r"t=1,\ldots,T")
            + " and variables "
            + math_inline(r"n=1,\ldots,N")
            + ". First, we compute the standardized features matrix "
            + math_inline("Z")
            + ", such that "
            + math_inline(r"Z_{t,n}=\sigma_n^{-1}(X_{t,n}-\mu_n)")
            + ", where "
            + math_inline(r"\mu_n")
            + " is the mean of "
            + math_inline(r"\{X_{t,n}\}_{t=1,\ldots,T}")
            + " and "
            + math_inline(r"\sigma_n")
            + " is the standard deviation of "
            + math_inline(r"\{X_{t,n}\}_{t=1,\ldots,T}")
            + ". Second, we compute the eigenvalues "
            + math_inline(r"\Lambda")
            + " and eigenvectors "
            + math_inline("W")
            + " such that "
            + math_inline(r"Z'ZW=W\Lambda")
            + ", where "
            + math_inline(r"\Lambda")
            + " is an "
            + math_inline(r"N\times N")
            + " diagonal matrix with main entries sorted in descending order, and "
            + math_inline("W")
            + " is an "
            + math_inline(r"N\times N")
            + " orthonormal matrix. Third, we derive the orthogonal features as "
            + math_inline("P=ZW")
            + ". We can verify the orthogonality of the features by noting that "
            + math_inline(r"P'P=W'Z'ZW=W'W\Lambda W'W=\Lambda")
            + ".</p>"
            "<p>The diagonalization is done on "
            + math_inline("Z")
            + " rather than "
            + math_inline("X")
            + ", for two reasons: (1) centering the data ensures that the first principal component is correctly oriented in the main direction of the observations. It is equivalent to adding an intercept in a linear regression; (2) re-scaling the data makes PCA focus on explaining correlations rather than variances. Without re-scaling, the first principal components would be dominated by the columns of "
            + math_inline("X")
            + " with highest variance, and we would not learn much about the structure or relationship between the variables. Snippet 8.5 computes the smallest number of orthogonal features that explain at least 95% of the variance of "
            + math_inline("Z")
            + ".</p>"
        )
    if stripped.startswith("Besides addressing substitution effects"):
        return (
            "<p>Besides addressing substitution effects, working with orthogonal features provides two additional benefits: (1) orthogonalization can also be used to reduce the dimensionality of the features matrix "
            + math_inline("X")
            + ", by dropping features associated with small eigenvalues. This usually speeds up the convergence of ML algorithms; (2) the analysis is conducted on features designed to explain the structure of the data.</p>"
            "<p>Let me stress this latter point. An ubiquitous concern throughout the book is the risk of overfitting. ML algorithms will always find a pattern, even if that pattern is a statistical fluke. You should always be skeptical about the purportedly important features identified by any method, including MDI, MDA, and SFI. Now, suppose that you derive orthogonal features using PCA. Your PCA analysis has determined that some features are more “principal” than others, without any knowledge of the labels (unsupervised learning). That is, PCA has ranked features without any possible overfitting in a classification sense. When your MDI, MDA, or SFI analysis selects as most important (using label information) the same features that PCA chose as principal (ignoring label information), this constitutes confirmatory evidence that the pattern identified by the ML algorithm is not entirely overfit.</p>"
            "<p>Figure 8.1 displays the scatter plot of eigenvalues associated with an eigenvector (x-axis) paired with MDI of the feature associated with an eigenvector (y-axis). The Pearson correlation is 0.8491 (p-value below 1E-150), evidencing that PCA identified informative features and ranked them correctly without overfitting.</p>"
        )
    if stripped.startswith("principal (ignoring label information)"):
        return (
            "<p>I find it useful to compute the weighted Kendall's tau between the feature importances and their associated eigenvalues (or equivalently, their inverse PCA rank). The closer this value is to 1, the stronger is the consistency between PCA ranking and feature importance ranking. One argument for preferring a weighted Kendall's tau over the standard Kendall is that we want to prioritize rank concordance among the most important features. We do not care so much about rank concordance among irrelevant (likely noisy) features. The hyperbolic-weighted Kendall's tau for the sample in Figure 8.1 is 0.8206.</p>"
            "<p>Snippet 8.6 shows how to compute this correlation using SciPy. In this example, sorting the features in descending importance gives us a PCA rank sequence very close to an ascending list. Because the <code>weightedtau</code> function gives higher weight to higher values, we compute the correlation on the inverse PCA ranking, <code>pcRank**-1</code>. The resulting weighted Kendall's tau is relatively high, at 0.8133.</p>"
        )
    if stripped.startswith("There are at least two research approaches"):
        return (
            "<p>There are at least two research approaches to feature importance. First, for each security "
            + math_inline("i")
            + " in an investment universe "
            + math_inline(r"i=1,\ldots,I")
            + ", we form a dataset "
            + math_inline(r"(X_i,y_i)")
            + ", and derive the feature importance in parallel. For example, let us denote "
            + math_inline(r"\lambda_{i,j,k}")
            + " the importance of feature "
            + math_inline("j")
            + " on instrument "
            + math_inline("i")
            + " according to criterion "
            + math_inline("k")
            + ". Then we can aggregate all results across the entire universe to derive a combined "
            + math_inline(r"\Lambda_{j,k}")
            + " importance of feature "
            + math_inline("j")
            + " according to criterion "
            + math_inline("k")
            + ". Features that are important across a wide variety of instruments are more likely to be associated with an underlying phenomenon, particularly when these feature importances exhibit high rank correlation across the criteria. It may be worth studying in-depth the theoretical mechanism that makes these features predictive.</p>"
            "<p>The main advantage of this approach is that it is computationally fast, as it can be parallelized. A disadvantage is that, due to substitution effects, important features may swap their ranks across instruments, increasing the variance of the estimated "
            + math_inline(r"\lambda_{i,j,k}")
            + ". This disadvantage becomes relatively minor if we average "
            + math_inline(r"\lambda_{i,j,k}")
            + " across instruments for a sufficiently large investment universe.</p>"
            "<p>A second alternative is what I call “features stacking.” It consists in stacking all datasets "
            + math_inline(r"\{(\widetilde X_i,y_i)\}_{i=1,\ldots,I}")
            + " into a single combined dataset "
            + math_inline(r"(X,y)")
            + ", where "
            + math_inline(r"\widetilde X_i")
            + " is a transformed instance of "
            + math_inline("X_i")
            + " (e.g., standardized on a rolling trailing window). The purpose of this transformation is to ensure some distributional homogeneity, "
            + math_inline(r"\widetilde X_i\sim X")
            + ". Under this approach, the classifier must learn what features are more important across all instruments simultaneously, as if the entire investment universe were in fact a single instrument.</p>"
            "<p>Features stacking presents some advantages: (1) The classifier will be fit on a much larger dataset than the one used with the parallelized (first) approach; (2) the importance is derived directly, and no weighting scheme is required for combining the results; (3) conclusions are more general and less biased by outliers or overfitting; and (4) because importance scores are not averaged across instruments, substitution effects do not cause the dampening of those scores.</p>"
            "<p>I usually prefer features stacking, not only for features importance but whenever a classifier can be fit on a set of instruments, including for the purpose of model prediction. That reduces the likelihood of overfitting an estimator to a particular instrument or small dataset. The main disadvantage of stacking is that it may consume a lot of memory and resources, however that is where a sound knowledge of HPC techniques will come in handy (Chapters 20-22).</p>"
        )
    if stripped.startswith("In this section, we are going to test"):
        return (
            "<p>In this section, we are going to test how these feature importance methods respond to synthetic data. We are going to generate a dataset "
            + math_inline(r"(X,y)")
            + " composed of three kinds of features:</p>"
        )
    if stripped.startswith("Snippet 8.7 shows"):
        return '<p>Snippet 8.7 shows how we can generate a synthetic dataset of 40 features where 10 are informative, 10 are redundant, and 20 are noise, on 10,000 observations. For details on how sklearn generates synthetic datasets, visit: <a href="http://scikit-learn.org/stable/modules/generated/sklearn.datasets.make_classification.html">http://scikit-learn.org/stable/modules/generated/sklearn.datasets.make_classification.html</a>.</p>'
    if stripped.startswith("Given that we know for certain"):
        return "<p>Given that we know for certain what feature belongs to each class, we can evaluate whether these three feature importance methods perform as designed. Now we need a function that can carry out each analysis on the same dataset. Snippet 8.8 accomplishes that, using bagged decision trees as default classifier (Chapter 6).</p>"
    if stripped.startswith("Figure 8.2 shows results"):
        return (
            "<p>Figure 8.2 shows results for MDI. For each feature, the horizontal bar indicates the mean MDI value across all the decision trees, and the horizontal line is the standard deviation of that mean. Since MDI importances add up to 1, if all features were equally important, each importance would have a value of "
            + math_inline(r"\frac{1}{40}")
            + ". The vertical dotted line marks that "
            + math_inline(r"\frac{1}{40}")
            + " threshold, separating features whose importance exceeds what would be expected from undistinguishable features. As you can see, MDI does a very good job in terms of placing all informative and redundant features above the red dotted line, with the exception of <code>R_5</code>, which did not make the cut by a small margin. Substitution effects cause some informative or redundant features to rank better than others, which was expected.</p>"
            + chapter_08_figure_html("8.3")
            + "<p>Figure 8.3 shows that MDA also did a good job. Results are consistent with those from MDI's in the sense that all the informed and redundant features rank better than the noise feature, with the exception of <code>R_6</code>, likely due to a substitution effect. One not so positive aspect of MDA is that the standard deviation of the means are somewhat higher, although that could be addressed by increasing the number of partitions in the purged "
            + math_inline("k")
            + "-fold CV, from, say, 10 to 100 (at the cost of "
            + math_inline(r"10\times")
            + " the computation time without parallelization).</p>"
            + chapter_08_figure_html("8.4")
            + "<p>Figure 8.4 shows that SFI also does a decent job; however, a few important features rank worse than noise (<code>I_6</code>, <code>I_2</code>, <code>I_9</code>, <code>I_1</code>, <code>I_3</code>, <code>R_5</code>), likely due to joint effects.</p>"
        )
    if stripped.startswith("The labels are a function"):
        return "<p>The labels are a function of a combination of features, and trying to forecast them independently misses the joint effects. Still, SFI is useful as a complement to MDI and MDA, precisely because both types of analyses are affected by different kinds of problems.</p>"
    return None


def chapter_09_code(text: str) -> str:
    return f"<code>{html.escape(text)}</code>"


def chapter_09_text_html(text: str) -> str:
    cleaned = text.strip()
    replacements = {
        "Begstra": "Bergstra",
        "crossentropy": "cross-entropy",
        "markto-market": "mark-to-market",
        "loglinear": "log-linear",
        "Pipelines :": "Pipelines:",
        "Stackoverflow": "Stack Overflow",
        "http://stackoverflow.com/questions/ 576169/": "http://stackoverflow.com/questions/576169/",
    }
    for old, new in replacements.items():
        cleaned = cleaned.replace(old, new)
    rendered = mathify_general_text(cleaned)
    for token in sorted(
        [
            "BaggingClassifier",
            "GridSearchCV",
            "MyPipeline",
            "Pipeline",
            "PurgedKFold",
            "RandomizedSearchCV",
            "clfHyperFit",
            "cvScore",
            "fit_params",
            "neg_log_loss",
            "param_grid",
            "sample_weight",
            "scikit-learn",
            "scoring='accuracy'",
            "scoring='f1'",
            "scoring='neg_log_loss'",
            "sklearn",
        ],
        key=len,
        reverse=True,
    ):
        rendered = rendered.replace(html.escape(token), chapter_09_code(token))
    return rendered


def chapter_09_p(text: str) -> str:
    return f"<p>{chapter_09_text_html(text)}</p>"


def chapter_09_footnote(number: int, url: str) -> str:
    escaped_url = html.escape(url)
    return f'<p class="footnote"><sup>{number}</sup> <a href="{escaped_url}">{escaped_url}</a>.</p>'


def chapter_09_paragraph_html(text: str) -> str | None:
    stripped = text.strip()
    suppress_exact = {
        "Hyper-Parameter Tuning with Cross-Validation",
        "fit_params[self.steps[-1][0]+'__sample_weight']=sample_weight return super(MyPipeline,self).fit(X,y,**fit_params)",
        "n=0 k=0",
        "1 http://scikit-learn.org/stable/modules/metrics.html. 2 http://scikit-learn.org/stable/auto_examples/svm/plot_rbf_parameters.html.",
        "3 http://scikit-learn.org/stable/modules/model_evaluation.html#log-loss.",
    }
    if stripped in suppress_exact:
        return ""
    suppress_prefixes = (
        "] distribution between",
        "0 for x < a",
        "⎪",
        "log ax logc ax",
        "(and tests) [in scipy.stats a random ] variable",
    )
    if stripped.startswith(suppress_prefixes):
        return ""
    if stripped.startswith("GridSearchCV. The argument"):
        return (
            "<p>Snippet 9.1 lists function "
            + chapter_09_code("clfHyperFit")
            + ", which implements a purged "
            + chapter_09_code("GridSearchCV")
            + ". The argument "
            + chapter_09_code("fit_params")
            + " can be used to pass "
            + chapter_09_code("sample_weight")
            + ", and "
            + chapter_09_code("param_grid")
            + " contains the values that will be combined into a grid. In addition, this function allows for the bagging of the tuned estimator. Bagging an estimator is generally a good idea for the reasons explained in Chapter 6, and the above function incorporates logic to that purpose.</p>"
            "<p>I advise you to use "
            + chapter_09_code("scoring='f1'")
            + " in the context of meta-labeling applications, for the following reason. Suppose a sample with a very large number of negative (i.e., label '0') cases. A classifier that predicts all cases to be negative will achieve high "
            + chapter_09_code("'accuracy'")
            + " or "
            + chapter_09_code("'neg_log_loss'")
            + ", even though it has not learned from the features how to discriminate between cases. In fact, such a model achieves zero recall and undefined precision (see Chapter 3, Section 3.7). The "
            + chapter_09_code("'f1'")
            + " score corrects for that performance inflation by scoring the classifier in terms of precision and recall (see Chapter 14, Section 14.8).</p>"
            "<p>For other (non-meta-labeling) applications, it is fine to use "
            + chapter_09_code("'accuracy'")
            + " or "
            + chapter_09_code("'neg_log_loss'")
            + ", because we are equally interested in predicting all cases. Note that a relabeling of cases has no impact on "
            + chapter_09_code("'accuracy'")
            + " or "
            + chapter_09_code("'neg_log_loss'")
            + ", however it will have an impact on "
            + chapter_09_code("'f1'")
            + ".</p>"
            "<p>This example introduces nicely one limitation of "
            + chapter_09_code("sklearn")
            + "'s Pipelines: Their "
            + chapter_09_code("fit")
            + " method does not expect a "
            + chapter_09_code("sample_weight")
            + " argument. Instead, it expects a "
            + chapter_09_code("fit_params")
            + " keyworded argument. That is a bug that has been reported in GitHub; however, it may take some time to fix it, as it involves rewriting and testing much functionality. Until then, feel free to use the workaround in Snippet 9.2.</p>"
        )
    if stripped.startswith("new class, called MyPipeline"):
        return (
            "<p>Snippet 9.2 creates a new class, called "
            + chapter_09_code("MyPipeline")
            + ", which inherits all methods from "
            + chapter_09_code("sklearn")
            + "'s "
            + chapter_09_code("Pipeline")
            + ". It overwrites the inherited "
            + chapter_09_code("fit")
            + " method with a new one that handles the argument "
            + chapter_09_code("sample_weight")
            + ", after which it redirects to the parent class.</p>"
        )
    if stripped.startswith("If you are not familiar"):
        return (
            '<p>If you are not familiar with this technique for expanding classes, you may want to read this introductory Stack Overflow post: '
            '<a href="http://stackoverflow.com/questions/576169/understanding-python-super-with-init-methods">'
            "http://stackoverflow.com/questions/576169/understanding-python-super-with-init-methods"
            "</a>.</p>"
        )
    if stripped.startswith("For ML algorithms with a large number of parameters"):
        return (
            "<p>For ML algorithms with a large number of parameters, a grid search cross-validation (CV) becomes computationally intractable. In this case, an alternative with good statistical properties is to sample each parameter from a distribution (Bergstra et al. [2011, 2012]). This has two benefits: First, we can control for the number of combinations we will search for, regardless of the dimensionality of the problem (the equivalent to a computational budget). Second, having parameters that are relatively irrelevant performance-wise will not substantially increase our search time, as would be the case with grid search CV.</p>"
            "<p>Rather than writing a new function to work with "
            + chapter_09_code("RandomizedSearchCV")
            + ", let us expand Snippet 9.1 to incorporate an option to this purpose. A possible implementation is Snippet 9.3.</p>"
        )
    if stripped.startswith("It is common for some ML algorithms"):
        return (
            "<p>It is common for some ML algorithms to accept non-negative hyper-parameters only. That is the case of some very popular parameters, such as "
            + math_inline("C")
            + " in the "
            + chapter_09_code("SVC")
            + " classifier and "
            + math_inline(r"\gamma")
            + " in the RBF kernel.<sup>1</sup> We could draw random numbers from a uniform distribution bounded between 0 and some large value, say 100. That would mean that 99% of the values would be expected to be greater than 1. That is not necessarily the most effective way of exploring the feasibility region of parameters whose functions do not respond linearly. For example, an "
            + chapter_09_code("SVC")
            + " can be as responsive to an increase in "
            + math_inline("C")
            + " from 0.01 to 1 as to an increase in "
            + math_inline("C")
            + " from 1 to 100.<sup>2</sup> So sampling "
            + math_inline("C")
            + " from a "
            + math_inline(r"U[0,100]")
            + " distribution will be inefficient. In those instances, it seems more effective to draw values from a distribution where the logarithm of those draws will be distributed uniformly. I call that a log-uniform distribution, and since I could not find it in the literature, I must define it properly.</p>"
            "<p>A random variable "
            + math_inline("x")
            + " follows a log-uniform distribution between "
            + math_inline("a>0")
            + " and "
            + math_inline("b>a")
            + " if and only if "
            + math_inline(r"\log[x]\sim U[\log[a],\log[b]]")
            + ". This distribution has a CDF:</p>"
            + math_display(
                r"F[x]=\begin{cases}"
                r"\dfrac{\log[x]-\log[a]}{\log[b]-\log[a]},& a\le x\le b,\\"
                r"0,& x<a,\\"
                r"1,& x>b."
                r"\end{cases}"
            )
            + "<p>From this, we derive a PDF:</p>"
            + math_display(
                r"f[x]=\begin{cases}"
                r"\dfrac{1}{x\log[b/a]},& a\le x\le b,\\"
                r"0,& x<a,\\"
                r"0,& x>b."
                r"\end{cases}"
            )
            + "<p>Note that the CDF is invariant to the base of the logarithm, since</p>"
            + math_display(r"\frac{\log[x/a]}{\log[b/a]}=\frac{\log_c[x/a]}{\log_c[b/a]}")
            + "<p>for any base "
            + math_inline("c")
            + ", thus the random variable is not a function of "
            + math_inline("c")
            + ". Snippet 9.4 implements (and tests) in "
            + chapter_09_code("scipy.stats")
            + " a random variable where "
            + math_inline(r"[a,b]=[1E-3,1E3]")
            + ", hence "
            + math_inline(r"\log[x]\sim U[\log[1E-3],\log[1E3]]")
            + ". Figure 9.1 illustrates the uniformity of the samples in log-scale.</p>"
            + chapter_09_footnote(1, "http://scikit-learn.org/stable/modules/metrics.html")
            + chapter_09_footnote(2, "http://scikit-learn.org/stable/auto_examples/svm/plot_rbf_parameters.html")
        )
    if stripped.startswith("Snippets 9.1 and 9.3 set scoring"):
        return (
            "<p>Snippets 9.1 and 9.3 set "
            + chapter_09_code("scoring='f1'")
            + " for meta-labeling applications. For other applications, they set "
            + chapter_09_code("scoring='neg_log_loss'")
            + " rather than the standard "
            + chapter_09_code("scoring='accuracy'")
            + ". Although accuracy has a more intuitive interpretation, I suggest that you use "
            + chapter_09_code("neg_log_loss")
            + " when you are tuning hyper-parameters for an investment strategy. Let me explain my reasoning.</p>"
            "<p>Suppose that your ML investment strategy predicts that you should buy a security, with high probability. You will enter a large long position, as a function of the strategy's confidence. If the prediction was erroneous, and the market sells off instead, you will lose a lot of money. And yet, accuracy accounts equally for an erroneous buy prediction with high probability and for an erroneous buy prediction with low probability. Moreover, accuracy can offset a miss with high probability with a hit with low probability.</p>"
            "<p>Investment strategies profit from predicting the right label with high confidence. Gains from good predictions with low confidence will not suffice to offset the losses from bad predictions with high confidence. For this reason, accuracy does not provide a realistic scoring of the classifier's performance. Conversely, log loss<sup>3</sup> (aka cross-entropy loss) computes the log-likelihood of the classifier given the true label, which takes predictions' probabilities into account. Log loss can be estimated as follows:</p>"
            + math_display(
                r"L[Y,P]=-\log[\operatorname{Prob}[Y\mid P]]"
                r"=-N^{-1}\sum_{n=0}^{N-1}\sum_{k=0}^{K-1}y_{n,k}\log[p_{n,k}]."
            )
            + chapter_09_footnote(3, "http://scikit-learn.org/stable/modules/model_evaluation.html#log-loss")
        )
    if stripped.startswith("Suppose that a classifier predicts two 1s"):
        return (
            "<p>Suppose that a classifier predicts two 1s, where the true labels are 1 and 0. The first prediction is a hit and the second prediction is a miss, thus accuracy is 50%. Figure 9.2 plots the cross-entropy loss when these predictions come from probabilities ranging "
            + math_inline("[0.5,0.9]")
            + ". One can observe that on the right side of the figure, log loss is large due to misses with high probability, even though the accuracy is 50% in all cases.</p>"
            "<p>There is a second reason to prefer cross-entropy loss over accuracy. CV scores a classifier by applying sample weights (see Chapter 7, Section 7.5). As you may recall from Chapter 4, observation weights were determined as a function of the observation's absolute return. The implication is that sample weighted cross-entropy loss estimates the classifier's performance in terms of variables involved in a PnL (mark-to-market profit and losses) calculation: It uses the correct label for the side, probability for the position size, and sample weight for the observation's return/outcome. That is the right ML performance metric for hyper-parameter tuning of financial applications, not accuracy.</p>"
        )
    if stripped.startswith("is the right ML performance metric"):
        return (
            "<p>When we use log loss as a scoring statistic, we often prefer to change its sign, hence referring to "
            + chapter_09_code("neg_log_loss")
            + ". The reason for this change is cosmetic, driven by intuition: A high neg log loss value is preferred to a low neg log loss value, just as with accuracy. Keep in mind this "
            + chapter_09_code("sklearn")
            + " bug when you use "
            + chapter_09_code("neg_log_loss")
            + ": <a href=\"https://github.com/scikit-learn/scikit-learn/issues/9144\">https://github.com/scikit-learn/scikit-learn/issues/9144</a>. To circumvent this bug, you should use the "
            + chapter_09_code("cvScore")
            + " function presented in Chapter 7.</p>"
        )
    if chapter_09_text_html(stripped) != mathify_general_text(stripped):
        return chapter_09_p(stripped)
    return None


def chapter_10_code(text: str) -> str:
    return f"<code>{html.escape(text)}</code>"


def chapter_10_footnote(number: int, content_html: str) -> str:
    return f'<p class="footnote"><sup>{number}</sup> {content_html}</p>'


def chapter_10_text_html(text: str) -> str:
    cleaned = text.strip()
    replacements = {
        "probabilities.</p>": "probabilities.</p>",
        "andprobabilities": "and-probabilities",
        "inflexion": "inflection",
        "Texas Hold’em": "Texas Hold'em",
        "in such way": "in such a way",
    }
    for old, new in replacements.items():
        cleaned = cleaned.replace(old, new)
    rendered = mathify_general_text(cleaned)
    for token in sorted(
        [
            "avgActiveSignals",
            "discreteSignal",
            "getSignal",
            "meta-labeling",
            "mpAvgActiveSignals",
            "stepSize",
            "t1",
        ],
        key=len,
        reverse=True,
    ):
        rendered = rendered.replace(html.escape(token), chapter_10_code(token))
    return rendered


def chapter_10_p(text: str) -> str:
    return f"<p>{chapter_10_text_html(text)}</p>"


def chapter_10_paragraph_html(text: str) -> str | None:
    stripped = text.strip()
    suppress_exact = {
        "2 Uncertainty is absolute when all outcomes are equally likely.",
        "This alternative presents the advantages that:",
    }
    if stripped in suppress_exact:
        return ""
    suppress_prefixes = (
        "[1, .5, 1.25], where pt is the price",
        "on {ct }, applying a method",
        "where F[x] is the CDF",
        "each label i = 1",
        "1 The references section lists",
        "usually these probabilities",
        "p̃ = maxi",
        "compute the test statistic",
        "the test statistic z =",
        "and where Z represents",
        "as m = x",
        "x (where the side is implied",
        "if 'side' in events:",
        "’’’ At time loc",
        "overtrading, I suggest",
        "discretizing the bet size",
        "where m [𝜔, x]",
        "1 j",
        "where L[fi",
        "We do not need to worry",
        "Snippet 10.4 implements",
        "ally these probabilities",
    )
    if stripped.startswith(suppress_prefixes):
        return ""
    if stripped.startswith("There are fascinating parallels"):
        return chapter_10_p(stripped)
    if stripped.startswith("Consider two strategies"):
        return (
            "<p>Consider two strategies on the same instrument. Let "
            + math_inline(r"m_{i,t}\in[-1,1]")
            + " be the bet size of strategy "
            + math_inline("i")
            + " at time "
            + math_inline("t")
            + ", where "
            + math_inline(r"m_{i,t}=-1")
            + " indicates a full short position and "
            + math_inline(r"m_{i,t}=1")
            + " indicates a full long position. Suppose that one strategy produced a sequence of bet sizes "
            + math_inline(r"[m_{1,1},m_{1,2},m_{1,3}]=[.5,1,0]")
            + ", as the market price followed a sequence "
            + math_inline(r"[p_1,p_2,p_3]=[1,.5,1.25]")
            + ", where "
            + math_inline("p_t")
            + " is the price at time "
            + math_inline("t")
            + ". The other strategy produced "
            + math_inline(r"[m_{2,1},m_{2,2},m_{2,3}]=[1,.5,0]")
            + ", as it was forced to reduce its bet size once the market moved against the initial full position. Both strategies produced forecasts that turned out to be correct (the price increased by 25% between "
            + math_inline("p_1")
            + " and "
            + math_inline("p_3")
            + "), however the first strategy made money (0.5) while the second strategy lost money (-.125).</p>"
            "<p>We would prefer to size positions in such a way that we reserve some cash for the possibility that the trading signal strengthens before it weakens. One option is to compute the series "
            + math_inline(r"c_t=c_{t,l}-c_{t,s}")
            + ", where "
            + math_inline(r"c_{t,l}")
            + " is the number of concurrent long bets at time "
            + math_inline("t")
            + ", and "
            + math_inline(r"c_{t,s}")
            + " is the number of concurrent short bets at time "
            + math_inline("t")
            + ". This bet concurrency is derived, for each side, similarly to how we computed label concurrency in Chapter 4 (recall the "
            + chapter_10_code("t1")
            + " object, with overlapping time spans). We fit a mixture of two Gaussians on "
            + math_inline(r"\{c_t\}")
            + ", applying a method like the one described in López de Prado and Foreman [2014]. Then, the bet size is derived as</p>"
            + math_display(
                r"m_t=\begin{cases}"
                r"\dfrac{F[c_t]-F[0]}{1-F[0]},& c_t\ge0,\\"
                r"\dfrac{F[c_t]-F[0]}{F[0]},& c_t<0."
                r"\end{cases}"
            )
            + "<p>where "
            + math_inline("F[x]")
            + " is the CDF of the fitted mixture of two Gaussians for a value "
            + math_inline("x")
            + ". For example, we could size the bet as 0.9 when the probability of observing a signal of greater value is only 0.1. The stronger the signal, the smaller the probability that the signal becomes even stronger, hence the greater the bet size.</p>"
            "<p>A second solution is to follow a budgeting approach. We compute the maximum number (or some other quantile) of concurrent long bets, "
            + math_inline(r"\max_i\{c_{i,l}\}")
            + ", and the maximum number of concurrent short bets, "
            + math_inline(r"\max_i\{c_{i,s}\}")
            + ". Then we derive the bet size as</p>"
            + math_display(r"m_t=\frac{c_{t,l}}{\max_i\{c_{i,l}\}}-\frac{c_{t,s}}{\max_i\{c_{i,s}\}},")
            + "<p>where "
            + math_inline(r"c_{t,l}")
            + " is the number of concurrent long bets at time "
            + math_inline("t")
            + ", and "
            + math_inline(r"c_{t,s}")
            + " is the number of concurrent short bets at time "
            + math_inline("t")
            + ". The goal is that the maximum position is not reached before the last concurrent signal is triggered.</p>"
            "<p>A third approach is to apply meta-labeling, as we explained in Chapter 3. We fit a classifier, such as an SVC or RF, to determine the probability of misclassification, and use that probability to derive the bet size.<sup>1</sup> This approach has a couple of advantages: First, the ML algorithm that decides the bet sizes is independent of the primary model, allowing for the incorporation of features predictive of false positives (see Chapter 3). Second, the predicted probability can be directly translated into bet size. Let us see how.</p>"
            + chapter_10_footnote(
                1,
                'The references section lists articles that explain how these probabilities are derived. Usually these probabilities incorporate information about the goodness of the fit, or confidence in the prediction. See Wu et al. [2004], and visit <a href="http://scikit-learn.org/stable/modules/svm.html#scores-and-probabilities">http://scikit-learn.org/stable/modules/svm.html#scores-and-probabilities</a>.',
            )
        )
    if stripped.startswith("Let us denote p [x]"):
        return (
            "<p>Let us denote "
            + math_inline("p[x]")
            + " the probability that label "
            + math_inline("x")
            + " takes place. For two possible outcomes, "
            + math_inline(r"x\in\{-1,1\}")
            + ", we would like to test the null hypothesis "
            + math_inline(r"H_0:p[x=1]=\frac{1}{2}")
            + ". We compute the test statistic</p>"
            + math_display(
                r"\begin{aligned}"
                r"z&=\frac{p[x=1]-\frac{1}{2}}{\sqrt{p[x=1](1-p[x=1])}}\\"
                r"&=\frac{2p[x=1]-1}{2\sqrt{p[x=1](1-p[x=1])}}\sim Z,"
                r"\end{aligned}"
            )
            + "<p>with "
            + math_inline(r"z\in(-\infty,+\infty)")
            + ", and where "
            + math_inline("Z")
            + " represents the standard Normal distribution. We derive the bet size as "
            + math_inline(r"m=2Z[z]-1")
            + ", where "
            + math_inline(r"m\in[-1,1]")
            + " and "
            + math_inline(r"Z[\cdot]")
            + " is the CDF of "
            + math_inline("Z")
            + ".</p>"
            "<p>For more than two possible outcomes, we follow a one-versus-rest method. Let "
            + math_inline(r"X=\{-1,\ldots,0,\ldots,1\}")
            + " be various labels associated with bet sizes, and "
            + math_inline(r"x\in X")
            + " the predicted label. In other words, the label is identified by the bet size associated with it. For each label "
            + math_inline(r"i=1,\ldots,\|X\|")
            + ", we estimate a probability "
            + math_inline("p_i")
            + ", with "
            + math_inline(r"\sum_{i=1}^{\|X\|}p_i=1")
            + ". We define "
            + math_inline(r"\tilde p=\max_i\{p_i\}")
            + " as the probability of "
            + math_inline("x")
            + ", and we would like to test for "
            + math_inline(r"H_0:\tilde p=\frac{1}{\|X\|}")
            + ".<sup>2</sup></p>"
            + math_display(
                r"z=\frac{\tilde p-\|X\|^{-1}}{\sqrt{\tilde p(1-\tilde p)}}\sim Z,\qquad z\in[0,+\infty)."
            )
            + "<p>We derive the bet size as "
            + math_inline(r"m=x\underbrace{(2Z[z]-1)}_{\in[0,1]}")
            + ", where "
            + math_inline(r"m\in[-1,1]")
            + " and "
            + math_inline(r"Z[z]")
            + " regulates the size for a prediction "
            + math_inline("x")
            + " (where the side is implied by "
            + math_inline("x")
            + "). Figure 10.1 plots the bet size as a function of test statistic.</p>"
            + chapter_10_figure_html("10.1")
            + "<p>Snippet 10.1 implements the translation from probabilities to bet size. It handles the possibility that the prediction comes from a meta-labeling estimator, as well from a standard labeling estimator. In step #2, it also averages active bets, and discretizes the final value, which we will explain in the following sections.</p>"
            + chapter_10_footnote(2, "Uncertainty is absolute when all outcomes are equally likely.")
        )
    if stripped.startswith("Every bet is associated"):
        return (
            "<p>Every bet is associated with a holding period, spanning from the time it originated to the time the first barrier is touched, "
            + math_inline("t_1")
            + " (see Chapter 3). One possible approach is to override an old bet as a new bet arrives; however, that is likely to lead to excessive turnover. A more sensible approach is to average all sizes across all bets still active at a given point in time. Snippet 10.2 illustrates one possible implementation of this idea.</p>"
        )
    if stripped.startswith("Averaging reduces some of the excess turnover"):
        return (
            "<p>Averaging reduces some of the excess turnover, but still it is likely that small trades will be triggered with every prediction. As this jitter would cause unnecessary overtrading, I suggest you discretize the bet size as "
            + math_inline(r"m^*=\operatorname{round}\left[\frac{m}{d}\right]d")
            + ", where "
            + math_inline(r"d\in(0,1]")
            + " determines the degree of discretization. Figure 10.2 illustrates the discretization of the bet size.</p>"
            + chapter_10_figure_html("10.2")
            + "<p>Snippet 10.3 implements this notion.</p>"
        )
    if stripped.startswith("Recall the triple-barrier labeling method"):
        return (
            "<p>Recall the triple-barrier labeling method presented in Chapter 3. Bar "
            + math_inline("i")
            + " is formed at time "
            + math_inline(r"t_{i,0}")
            + ", at which point we forecast the first barrier that will be touched. That prediction implies a forecasted price, "
            + math_inline(r"E_{t_{i,0}}[p_{t_{i,1}}]")
            + ", consistent with the barriers' settings. In the period elapsed until the outcome takes place, "
            + math_inline(r"t\in[t_{i,0},t_{i,1}]")
            + ", the price "
            + math_inline("p_t")
            + " fluctuates and additional forecasts may be formed, "
            + math_inline(r"E_{t_{j,0}}[p_{t_{i,1}}]")
            + ", where "
            + math_inline(r"j\in[i+1,I]")
            + " and "
            + math_inline(r"t_{j,0}\le t_{i,1}")
            + ". In Sections 10.4 and 10.5 we discussed methods for averaging the active bets and discretizing the bet size as new forecasts are formed.</p>"
            "<p>In this section we will introduce an approach to adjust bet sizes as market price "
            + math_inline("p_t")
            + " and forecast price "
            + math_inline("f_i")
            + " fluctuate. In the process, we will derive the order's limit price. Let "
            + math_inline("q_t")
            + " be the current position, "
            + math_inline("Q")
            + " the maximum absolute position size, and "
            + math_inline(r"\hat q_{i,t}")
            + " the target position size associated with forecast "
            + math_inline("f_i")
            + ", such that</p>"
            + math_display(
                r"\begin{aligned}"
                r"\hat q_{i,t}&=\operatorname{int}\!\left[m[\omega,f_i-p_t]Q\right],\\"
                r"m[\omega,x]&=\frac{x}{\sqrt{\omega+x^2}}."
                r"\end{aligned}"
            )
            + "<p>where "
            + math_inline(r"m[\omega,x]")
            + " is the bet size, "
            + math_inline(r"x=f_i-p_t")
            + " is the divergence between the current market price and the forecast, "
            + math_inline(r"\omega")
            + " is a coefficient that regulates the width of the sigmoid function, and "
            + math_inline(r"\operatorname{int}[x]")
            + " is the integer value of "
            + math_inline("x")
            + ". Note that for a real-valued price divergence "
            + math_inline("x")
            + ", "
            + math_inline(r"-1<m[\omega,x]<1")
            + "; the integer value "
            + math_inline(r"\hat q_{i,t}")
            + " is bounded "
            + math_inline(r"-Q<\hat q_{i,t}<Q")
            + ".</p>"
            "<p>The target position size "
            + math_inline(r"\hat q_{i,t}")
            + " can be dynamically adjusted as "
            + math_inline("p_t")
            + " changes. In particular, as "
            + math_inline(r"p_t\to f_i")
            + " we get "
            + math_inline(r"\hat q_{i,t}\to0")
            + ", because the algorithm wants to realize the gains. This implies a breakeven limit price "
            + math_inline(r"\bar p")
            + " for the order size "
            + math_inline(r"\hat q_{i,t}-q_t")
            + ", to avoid realizing losses. In particular,</p>"
            + math_display(
                r"\bar p=\frac{1}{|\hat q_{i,t}-q_t|}"
                r"\sum_{j=|q_t+\operatorname{sgn}[\hat q_{i,t}-q_t]|}^{|\hat q_{i,t}|}"
                r"L\!\left[f_i,\omega,\frac{j}{Q}\right]."
            )
            + "<p>where "
            + math_inline(r"L[f_i,\omega,m]")
            + " is the inverse function of "
            + math_inline(r"m[\omega,f_i-p_t]")
            + " with respect to "
            + math_inline("p_t")
            + ",</p>"
            + math_display(r"L[f_i,\omega,m]=f_i-m\sqrt{\frac{\omega}{1-m^2}}.")
            + "<p>We do not need to worry about the case "
            + math_inline(r"m^2=1")
            + ", because the normalized bet size used by the inverse is strictly inside "
            + math_inline(r"(-1,1)")
            + ". Since this function is monotonic, the algorithm cannot realize losses as "
            + math_inline(r"p_t\to f_i")
            + ".</p>"
            "<p>Let us calibrate "
            + math_inline(r"\omega")
            + ". Given a user-defined pair "
            + math_inline(r"(x,m^*)")
            + ", such that "
            + math_inline(r"x=f_i-p_t")
            + " and "
            + math_inline(r"m^*=m[\omega,x]")
            + ", the inverse function of "
            + math_inline(r"m[\omega,x]")
            + " with respect to "
            + math_inline(r"\omega")
            + " is</p>"
            + math_display(r"\omega=x^2\left((m^*)^{-2}-1\right).")
            + "<p>Snippet 10.4 implements the algorithm that computes the dynamic position size and limit prices as a function of "
            + math_inline("p_t")
            + " and "
            + math_inline("f_i")
            + ". First, we calibrate the sigmoid function, so that it returns a bet size of "
            + math_inline(r"m^*=.95")
            + " for a price divergence of "
            + math_inline("x=10")
            + ". Second, we compute the target position "
            + math_inline(r"\hat q_{i,t}")
            + " for a maximum position "
            + math_inline("Q=100")
            + ", "
            + math_inline("f_i=115")
            + " and "
            + math_inline("p_t=100")
            + ". If you try "
            + math_inline("f_i=110")
            + ", you will get "
            + math_inline(r"\hat q_{i,t}=95")
            + ", consistent with the calibration of "
            + math_inline(r"\omega")
            + ". Third, the limit price for this order of size "
            + math_inline(r"\hat q_{i,t}-q_t=97")
            + " is "
            + math_inline(r"\bar p=112.3657")
            + ", satisfying "
            + math_inline(r"p_t<\bar p<f_i")
            + ". It is between the current price and the forecasted price.</p>"
        )
    if stripped.startswith("As an alternative to the sigmoid function"):
        return (
            "<p>As an alternative to the sigmoid function, we could have used a power function "
            + math_inline(r"\tilde m[\omega,x]=\operatorname{sgn}[x]|x|^\omega")
            + ", where "
            + math_inline(r"\omega\ge0")
            + ", "
            + math_inline(r"x\in[-1,1]")
            + ", which results in "
            + math_inline(r"\tilde m[\omega,x]\in[-1,1]")
            + ". This alternative presents the advantages that:</p>"
        )
    if stripped.startswith("We leave the derivation"):
        return (
            "<p>We leave the derivation of the equations for a power function as an exercise. Figure 10.3 plots the bet sizes (y-axis) as a function of price divergence "
            + math_inline(r"f-p_t")
            + " (x-axis) for both the sigmoid and power functions.</p>"
            + chapter_10_figure_html("10.3")
        )
    if chapter_10_text_html(stripped) != mathify_general_text(stripped):
        return chapter_10_p(stripped)
    return None


def chapter_11_footnote(number: int, content_html: str) -> str:
    return f'<p class="footnote"><sup>{number}</sup> {content_html}</p>'


def chapter_11_figure_html(number: str) -> str:
    figures = {
        "11.1": (
            "media/chapter-11-figure-11-1.png",
            "Figure 11.1: Best Sharpe ratio in-sample (SR IS) vs Sharpe ratio out-of-sample (SR OOS)",
        ),
        "11.2": (
            "media/chapter-11-figure-11-2.png",
            "Figure 11.2: Probability of backtest overfitting derived from the distribution of logits",
        ),
    }
    src, caption = figures[number]
    return f'<figure class="book-figure"><img src="{src}" alt="{html.escape(caption)}"><figcaption>{html.escape(caption)}</figcaption></figure>'


def chapter_11_snippet_html() -> str:
    return (
        '<figure class="quote-snippet">'
        "<figcaption>Snippet 11.1: Marcos' Second Law of Backtesting</figcaption>"
        "<blockquote>"
        "<p>Backtesting while researching is like drinking and driving.<br>"
        "Do not research under the influence of a backtest.</p>"
        "</blockquote>"
        '<p class="quote-attribution">Marcos López de Prado, <em>Advances in Financial Machine Learning</em> (2018)</p>'
        "</figure>"
    )


def chapter_11_text_html(text: str) -> str:
    cleaned = text.strip()
    replacements = {
        "crossvalidation": "cross-validation",
        "ignor- ing": "ignoring",
        "opti- mization": "optimization",
        "per- formance": "performance",
        "out-of-sample)": "out-of-sample)",
        "timefolds method.2": "time-folds method",
        "(TxN)": r"\(T\times N\)",
        "S∕2": r"\(S/2\)",
        "CS ": r"\(C_S\) ",
        " c ∈ CS": r" \(c\in C_S\)",
        "𝜆": r"\(\lambda\)",
        "PBO": r"\(\mathrm{PBO}\)",
    }
    for source, target in replacements.items():
        cleaned = cleaned.replace(source, target)
    return mathify_general_text(cleaned)


def chapter_11_strategy_selection_intro_html() -> str:
    return (
        "<p>In Chapter 7 we discussed how the presence of serial conditionality in labels defeats standard "
        "k-fold cross-validation, because the random sampling will spatter redundant observations into both "
        "the training and testing sets. We must find a different true out-of-sample validation procedure: a "
        "procedure that evaluates our model on the observations least likely to be correlated or redundant to "
        "those used to train the model. See Arlot and Celisse [2010] for a survey.</p>"
        "<p>Scikit-learn has implemented a walk-forward time-folds method. Under this approach, testing moves "
        "forward in the time direction with the goal of preventing leakage. This is consistent with the way "
        "historical backtests and trading are done. However, in the presence of long-range serial dependence, "
        "testing one observation away from the end of the training set may not suffice to avoid informational "
        "leakage. We will retake this point in Chapter 12, Section 12.2.</p>"
        "<p>One disadvantage of the walk-forward method is that it can be easily overfit. The reason is that "
        "without random sampling, there is a single path of testing that can be repeated over and over until a "
        "false positive appears. Like in standard CV, some randomization is needed to avoid this sort of "
        "performance targeting or backtest optimization, while avoiding the leakage of examples correlated to "
        "the training set into the testing set. Next, we will introduce a CV method for strategy selection, "
        "based on the estimation of the probability of backtest overfitting (PBO). We leave for Chapter 12 an "
        "explanation of CV methods for backtesting.</p>"
        "<p>Bailey et al. [2017a] estimate the PBO through the combinatorially "
        "symmetric cross-validation (CSCV) method. Schematically, this procedure works as follows.</p>"
        "<p>First, we form a matrix "
        + math_inline("M")
        + " by collecting the performance series from the "
        + math_inline("N")
        + " trials. In particular, each column "
        + math_inline(r"n=1,\ldots,N")
        + " represents a vector of PnL over "
        + math_inline(r"t=1,\ldots,T")
        + " observations associated with a particular model configuration tried by the researcher. "
        + math_inline("M")
        + " is therefore a real-valued matrix of order "
        + math_inline(r"T\times N")
        + ". The only conditions we impose are that (1) "
        + math_inline("M")
        + " is a true matrix, with the same number of rows for each column, where observations are synchronous "
        "for every row across the "
        + math_inline("N")
        + " trials, and (2) the performance evaluation metric used to choose the optimal strategy can be "
        "estimated on subsamples of each column. For example, if that metric is the Sharpe ratio, we assume "
        "that the IID Normal distribution assumption can be held on various slices of the reported performance. "
        "If different model configurations trade with different frequencies, observations are aggregated "
        "to match a common index "
        + math_inline(r"t=1,\ldots,T")
        + ".</p>"
        "<p>Second, we partition "
        + math_inline("M")
        + " across rows, into an even number "
        + math_inline("S")
        + " of disjoint submatrices of equal dimensions. Each of these submatrices "
        + math_inline("M_s")
        + ", with "
        + math_inline(r"s=1,\ldots,S")
        + ", is of order "
        + math_inline(r"(T/S)\times N")
        + ".</p>"
        "<p>Third, we form all combinations "
        + math_inline("C_S")
        + " of "
        + math_inline("M_s")
        + ", taken in groups of size "
        + math_inline("S/2")
        + ". This gives a total number of combinations</p>"
        + math_display(
            r"\begin{aligned}"
            r"\binom{S}{S/2}&=\binom{S-1}{S/2-1}\frac{S}{S/2}\\"
            r"&=\cdots\\"
            r"&=\prod_{i=0}^{S/2-1}\frac{S-i}{S/2-i}."
            r"\end{aligned}"
        )
    )


def chapter_11_strategy_selection_tail_html() -> str:
    return (
        "<p>For instance, if "
        + math_inline("S=16")
        + ", we will form 12,780 combinations. Each combination "
        + math_inline(r"c\in C_S")
        + " is composed of "
        + math_inline("S/2")
        + " submatrices "
        + math_inline("M_s")
        + ". Fourth, for each combination "
        + math_inline(r"c\in C_S")
        + ", we:</p>"
        '<ol class="algorithm-list">'
        "<li>Form the training set "
        + math_inline("J")
        + ", by joining the "
        + math_inline("S/2")
        + " submatrices "
        + math_inline("M_s")
        + " that constitute "
        + math_inline("c")
        + ". "
        + math_inline("J")
        + " is a matrix of order "
        + math_inline(r"(T/S)(S/2)\times N=(T/2)\times N")
        + ".</li>"
        "<li>Form the testing set "
        + math_inline(r"\bar J")
        + ", as the complement of "
        + math_inline("J")
        + " in "
        + math_inline("M")
        + ". In other words, "
        + math_inline(r"\bar J")
        + " is the "
        + math_inline(r"(T/2)\times N")
        + " matrix formed by all rows of "
        + math_inline("M")
        + " that are not part of "
        + math_inline("J")
        + ".</li>"
        "<li>Form a vector "
        + math_inline("R")
        + " of performance statistics of order "
        + math_inline("N")
        + ", where the "
        + math_inline("n")
        + "-th item of "
        + math_inline("R")
        + " reports the performance associated with the "
        + math_inline("n")
        + "-th column of "
        + math_inline("J")
        + " (the training set).</li>"
        "<li>Determine the element "
        + math_inline("n^*")
        + " such that "
        + math_inline(r"R_n\le R_{n^*},\ \forall n=1,\ldots,N")
        + ". In other words, "
        + math_inline(r"n^*=\arg\max_n\{R_n\}")
        + ".</li>"
        "<li>Form a vector "
        + math_inline(r"\bar R")
        + " of performance statistics of order "
        + math_inline("N")
        + ", where the "
        + math_inline("n")
        + "-th item of "
        + math_inline(r"\bar R")
        + " reports the performance associated with the "
        + math_inline("n")
        + "-th column of "
        + math_inline(r"\bar J")
        + " (the testing set).</li>"
        "<li>Determine the relative rank of "
        + math_inline(r"\bar R_{n^*}")
        + " within "
        + math_inline(r"\bar R")
        + ". We denote this relative rank as "
        + math_inline(r"\bar\omega_c")
        + ", where "
        + math_inline(r"\bar\omega_c\in(0,1)")
        + ". This is the relative rank of the out-of-sample (OOS) performance associated with the trial chosen "
        "in-sample (IS). If the strategy optimization procedure does not overfit, we should observe that "
        + math_inline(r"\bar R_{n^*}")
        + " systematically outperforms "
        + math_inline(r"\bar R")
        + " OOS, just as "
        + math_inline(r"R_{n^*}")
        + " outperformed "
        + math_inline("R")
        + " IS.</li>"
        "<li>Define the logit "
        + math_inline(r"\lambda_c=\log\left[\frac{\bar\omega_c}{1-\bar\omega_c}\right]")
        + ". This presents the property that "
        + math_inline(r"\lambda_c=0")
        + " when "
        + math_inline(r"\bar R_{n^*}")
        + " coincides with the median of "
        + math_inline(r"\bar R")
        + ". High logit values imply consistency between IS and OOS performance, which indicates a low level "
        "of backtest overfitting.</li>"
        "</ol>"
        "<p>Fifth, compute the distribution of ranks OOS by collecting all the "
        + math_inline(r"\lambda_c")
        + ", for "
        + math_inline(r"c\in C_S")
        + ". The probability distribution function "
        + math_inline(r"f(\lambda)")
        + " is then estimated as the relative frequency at which "
        + math_inline(r"\lambda")
        + " occurred across all "
        + math_inline("C_S")
        + ", with</p>"
        + math_display(
            r"\int_{-\infty}^{\infty} f(\lambda)\,d\lambda=1,\qquad "
            r"\mathrm{PBO}=\int_{-\infty}^{0} f(\lambda)\,d\lambda."
        )
        + "<p>The PBO is the probability associated with IS-optimal strategies that underperform OOS. "
        "The x-axis of Figure 11.1 shows the Sharpe ratio IS from the best strategy selected. The y-axis "
        "shows the Sharpe ratio OOS for that same best strategy selected. There is a strong and persistent "
        "performance decay, caused by backtest overfitting. Applying the above algorithm, we can derive the "
        "PBO associated with this strategy selection process, as displayed in Figure 11.2. The observations "
        "in each subset preserve the original time sequence. The random sampling is done on the relatively "
        "uncorrelated subsets, rather than on the observations. See Bailey et al. "
        "[2017a] for an experimental analysis of the accuracy of this methodology.</p>"
        + chapter_11_figure_html("11.1")
        + chapter_11_figure_html("11.2")
    )


def chapter_11_paragraph_html(text: str) -> str | None:
    stripped = text.strip()
    if stripped.startswith("Backtesting is one of the most essential"):
        return (
            "<p>Backtesting is one of the most essential, and yet least understood, techniques in the quant arsenal. "
            "A common misunderstanding is to think of backtesting as a research tool. Researching and backtesting is "
            "like drinking and driving. Do not research under the influence of a backtest. Most backtests published "
            "in journals are flawed, as the result of selection bias on multiple tests (Bailey, Borwein, López de "
            "Prado, and Zhu [2014]; Harvey et al. [2016]). "
            "A full book could be written listing all the different errors people make while backtesting. I may be "
            "the academic author with the largest number of journal articles on backtesting<sup>1</sup> and investment "
            "performance metrics, and still I do not feel I would have the stamina to compile all the different errors "
            "I have seen over the past 20 years. This chapter is not a crash course on backtesting, but a short list "
            "of some of the common errors that even seasoned professionals make.</p>"
            + chapter_11_footnote(
                1,
                '<a href="http://papers.ssrn.com/sol3/cf_dev/AbsByAuth.cfm?per_id=434076">http://papers.ssrn.com/sol3/cf_dev/AbsByAuth.cfm?per_id=434076</a>; '
                '<a href="http://www.QuantResearch.org/">http://www.QuantResearch.org/</a>.',
            )
        )
    if stripped.startswith("1 http://papers.ssrn.com") or stripped == "PROBABLY WRONG":
        return ""
    if stripped.startswith("Chapter 8 discussed substitution effects"):
        return (
            "<p>Chapter 8 discussed substitution effects, joint effects, masking, MDI, MDA, SFI, parallelized features, stacked features, etc. Even if some features are very important, it does not mean that they can be monetized through an investment strategy. Conversely, there are plenty of strategies that will appear to be profitable even though they are based on irrelevant features. Feature importance is a true research tool, because it helps us understand the nature of the patterns uncovered by the ML algorithm, regardless of their monetization. Critically, feature importance is derived ex-ante, before the historical performance is simulated. In contrast, a backtest is not a research tool. It provides us with very little insight into the reason why a particular strategy would have made money. Just as a lottery winner may feel he has done something to deserve his luck, there is always some ex-post story (Luo's sin number three). Authors claim to have found hundreds of “alphas” and “factors,” and there is always some convoluted explanation for them. Instead, what they have found are the lottery tickets that won the last game. The winner has cashed out, and those numbers are useless for the next round. If you would not pay extra for those lottery tickets, why would you care about those hundreds of alphas? Those authors never tell us about all the tickets that were sold, that is, the millions of simulations it took to find these “lucky” alphas.</p>"
            "<p>The purpose of a backtest is to discard bad models, not to improve them. Adjusting your model based on the backtest results is a waste of time ... and it is dangerous. Invest your time and effort in getting all the components right, as we have discussed elsewhere in the book: structured data, labeling, weighting, ensembles, cross-validation, feature importance, bet sizing, etc. By the time you are backtesting, it is too late. Never backtest until your model has been fully specified. If the backtest fails, start all over. If you do that, the chances of finding a false discovery will drop substantially, but still they will not be zero.</p>"
        )
    if stripped.startswith("In Chapter 7 we discussed how"):
        return chapter_11_strategy_selection_intro_html()
    if stripped.startswith("2 2 S∕") or stripped.startswith("SR OOS") or stripped.startswith("SR IS"):
        return ""
    if stripped.startswith("Prob Overfit=0.74") or stripped == "Frequency" or stripped == "Logits":
        return ""
    if stripped.startswith("For instance, if S = 16"):
        return chapter_11_strategy_selection_tail_html()
    if stripped.startswith("Fifth, compute the distribution") or stripped.startswith("f (𝜆)d𝜆 = 1"):
        return ""
    if stripped.startswith("that underperform OOS."):
        return ""
    if stripped.startswith("Do not research under the influence of a backtest."):
        return ""
    fixed = chapter_11_text_html(stripped)
    if fixed != mathify_general_text(stripped):
        return f"<p>{fixed}</p>"
    return None


def chapter_11_block_figure_html(block: Block) -> str | None:
    if block.caption.startswith("Figure 11.1") or block.caption.startswith("Figure 11.2"):
        return ""
    if block.src == "media/afml-184_1.jpg":
        return ""
    return None


def chapter_12_cpcv_table(assignments: bool) -> str:
    headers = ["Group"] + [f"S{i}" for i in range(1, 16)] + ["Paths"]
    if assignments:
        marks = {
            "G1": {1: "1", 2: "2", 3: "3", 4: "4", 5: "5"},
            "G2": {1: "1", 6: "2", 7: "3", 8: "4", 9: "5"},
            "G3": {2: "1", 6: "2", 10: "3", 11: "4", 12: "5"},
            "G4": {3: "1", 7: "2", 10: "3", 13: "4", 14: "5"},
            "G5": {4: "1", 8: "2", 11: "3", 13: "4", 15: "5"},
            "G6": {5: "1", 9: "2", 12: "3", 14: "4", 15: "5"},
        }
    else:
        marks = {
            "G1": {i: "x" for i in [1, 2, 3, 4, 5]},
            "G2": {i: "x" for i in [1, 6, 7, 8, 9]},
            "G3": {i: "x" for i in [2, 6, 10, 11, 12]},
            "G4": {i: "x" for i in [3, 7, 10, 13, 14]},
            "G5": {i: "x" for i in [4, 8, 11, 13, 15]},
            "G6": {i: "x" for i in [5, 9, 12, 14, 15]},
        }
    rows = []
    for group, row_marks in marks.items():
        cells = [f'<th scope="row">{group}</th>']
        cells.extend(f"<td>{row_marks.get(i, '')}</td>" for i in range(1, 16))
        cells.append("<td>5</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return (
        '<div class="table-wrap"><table class="semantic-table cpcv-table">'
        "<thead><tr>"
        + "".join(f"<th>{header}</th>" for header in headers)
        + "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table></div>"
    )


def chapter_12_figure_html(number: str) -> str:
    if number == "12.1":
        caption = "Figure 12.1: Paths generated for " + math_inline(r"\varphi[6,2]=5")
        return (
            '<figure class="table-figure cpcv-figure"><figcaption>'
            + caption
            + "</figcaption>"
            + chapter_12_cpcv_table(assignments=False)
            + "</figure>"
        )
    caption = "Figure 12.2: Assignment of testing groups to each of the 5 paths"
    return (
        '<figure class="table-figure cpcv-figure"><figcaption>'
        + html.escape(caption)
        + "</figcaption>"
        + chapter_12_cpcv_table(assignments=True)
        + "</figure>"
    )


def chapter_12_text_html(text: str) -> str:
    cleaned = text.strip()
    replacements = {
        "outof-sample": "out-of-sample",
        "histori- cal": "historical",
        "compara- ble": "comparable",
        "train- ing": "training",
        "respec- tive": "respective",
        "datapoints": "data points",
        "walk-backwards": "walk-backward",
        "𝜑": r"\varphi",
        "𝜃": r"\theta",
        "𝜌̄i": r"\bar\rho_i",
    }
    for source, target in replacements.items():
        cleaned = cleaned.replace(source, target)
    return mathify_general_text(cleaned)


def chapter_12_p(text: str) -> str:
    return f"<p>{chapter_12_text_html(text)}</p>"


def chapter_12_wf_pitfalls_html() -> str:
    return (
        "<p>WF suffers from three major disadvantages: First, a single scenario is tested (the historical path), "
        "which can be easily overfit (Bailey et al. [2014]). Second, WF is not necessarily representative of "
        "future performance, as results can be biased by the particular sequence of data points. Proponents of "
        "the WF method typically argue that predicting the past would lead to overly optimistic performance "
        "estimates. And yet, very often fitting an outperforming model on the reversed sequence of observations "
        "will lead to an underperforming WF backtest. The truth is, it is as easy to overfit a walk-forward "
        "backtest as to overfit a walk-backward backtest, and the fact that changing the sequence of observations "
        "yields inconsistent outcomes is evidence of that overfitting. If proponents of WF were right, we should "
        "observe that walk-backward backtests systematically outperform their walk-forward counterparts. That is "
        "not the case, hence the main argument in favor of WF is rather weak.</p>"
        "<p>To make this second disadvantage clearer, suppose an equity strategy that is backtested with a WF on "
        "S&amp;P 500 data, starting January 1, 2007. Until March 15, 2009, the mix of rallies and sell-offs will "
        "train the strategy to be market neutral, with low confidence on every position. After that, the long "
        "rally will dominate the dataset, and by January 1, 2017, buy forecasts will prevail over sell forecasts. "
        "The performance would be very different had we played the information backwards, from January 1, 2017 "
        "to January 1, 2007. By exploiting a particular sequence, a strategy selected by WF may set us up for a "
        "debacle.</p>"
        "<p>The third disadvantage of WF is that the initial decisions are made on a smaller portion of the total "
        "sample. Even if a warm-up period is set, most of the information is used by only a small portion of the "
        "decisions. Consider a strategy with a warm-up period that uses "
        + math_inline("t_0")
        + " observations out of "
        + math_inline("T")
        + ". This strategy makes half of its decisions, "
        + math_inline(r"(T-t_0)/2")
        + ", on an average number of data points,</p>"
        + math_display(
            r"\left(\frac{T-t_0}{2}\right)^{-1}"
            r"\left(t_0+\frac{T+t_0}{2}\right)\frac{T-t_0}{4}"
            r"=\frac{1}{4}T+\frac{3}{4}t_0"
        )
        + "<p>which is only "
        + math_inline(r"\frac{3}{4}\frac{t_0}{T}+\frac{1}{4}")
        + " fraction of the observations. Although this problem is attenuated by increasing the warm-up period, "
        "doing so also reduces the length of the backtest.</p>"
    )


def chapter_12_cv_intro_html() -> str:
    return (
        "<p>Investors often ask how a strategy would perform if subjected to a stress scenario as unforeseeable "
        "as the 2008 crisis, or the dot-com bubble, or the taper tantrum, or the China scare of 2015-2016, etc. "
        "One way to answer is to split the observations into two sets, one with the period we wish to test "
        "(testing set), and one with the rest (training set). For example, a classifier would be trained on the "
        "period January 1, 2009-January 1, 2017, then tested on the period January 1, 2008-December 31, 2008. "
        "The performance we will obtain for 2008 is not historically accurate, since the classifier was trained "
        "on data that was only available after 2008. But historical accuracy was not the goal of the test. The "
        "objective of the test was to subject a strategy ignorant of 2008 to a stress scenario such as 2008.</p>"
        "<p>The goal of backtesting through cross-validation (CV) is not to derive historically accurate "
        "performance, but to infer future performance from a number of out-of-sample scenarios. For each period "
        "of the backtest, we simulate the performance of a classifier that knew everything except for that period.</p>"
    )


def chapter_12_combinatorial_splits_html() -> str:
    return (
        "<p>Consider "
        + math_inline("T")
        + " observations partitioned into "
        + math_inline("N")
        + " groups without shuffling, where groups "
        + math_inline(r"n=1,\ldots,N-1")
        + " are of size "
        + math_inline(r"\lfloor T/N\rfloor")
        + ", the "
        + math_inline("N")
        + "th group is of size "
        + math_inline(r"T-\lfloor T/N\rfloor(N-1)")
        + ", and "
        + math_inline(r"\lfloor\cdot\rfloor")
        + " is the floor or integer function. For a testing set of size "
        + math_inline("k")
        + " groups, the number of possible training/testing splits is</p>"
        + math_display(
            r"\binom{N}{N-k}=\frac{\prod_{i=0}^{k-1}(N-i)}{k!}."
        )
    )


def chapter_12_paths_formula_html() -> str:
    return (
        "<p>Since each combination involves "
        + math_inline("k")
        + " tested groups, the total number of tested groups is "
        + math_inline(r"k\binom{N}{N-k}")
        + ". And since we have computed all possible combinations, these tested groups are uniformly distributed "
        "across all "
        + math_inline("N")
        + " groups. The implication is that from "
        + math_inline("k")
        + "-sized testing sets on "
        + math_inline("N")
        + " groups we can backtest a total number of paths "
        + math_inline(r"\varphi[N,k]")
        + ",</p>"
        + math_display(
            r"\varphi[N,k]=\frac{k}{N}\binom{N}{N-k}"
            r"=\frac{\prod_{i=1}^{k-1}(N-i)}{(k-1)!}."
        )
    )


def chapter_12_figure_explanation_html() -> str:
    return (
        "<p>Figure 12.1 illustrates the composition of train/test splits for "
        + math_inline("N=6")
        + " and "
        + math_inline("k=2")
        + ". There are "
        + math_inline(r"\binom{6}{4}=15")
        + " splits, indexed as "
        + math_inline(r"S_1,\ldots,S_{15}")
        + ". For each split, the figure marks with a cross (x) the groups included in the testing set, and leaves "
        "unmarked the groups that form the training set. Each group forms part of "
        + math_inline(r"\varphi[6,2]=5")
        + " testing sets, therefore this train/test split scheme allows us to compute 5 backtest paths.</p>"
        "<p>Figure 12.2 shows the assignment of each tested group to one backtest path.</p>"
    )


def chapter_12_path_examples_html() -> str:
    return (
        "<p>For example, the first two paths combine forecasts from the following testing groups:</p>"
        + math_display(
            r"\begin{aligned}"
            r"\text{Path 1}:&\ (G_1,S_1),(G_2,S_1),(G_3,S_2),\\"
            r"&\ (G_4,S_3),(G_5,S_4),(G_6,S_5),\\"
            r"\text{Path 2}:&\ (G_1,S_2),(G_2,S_6),(G_3,S_6),\\"
            r"&\ (G_4,S_7),(G_5,S_8),(G_6,S_9)."
            r"\end{aligned}"
        )
        + "<p>and so on.</p>"
        "<p>These paths are generated by training the classifier on a portion "
        + math_inline(r"\theta=1-\frac{k}{N}")
        + " of the data for each combination. Although it is theoretically possible to train on a portion "
        + math_inline(r"\theta<\frac{1}{2}")
        + ", in practice we will assume that "
        + math_inline(r"k\le N/2")
        + ". The portion of data in the training set "
        + math_inline(r"\theta")
        + " increases with "
        + math_inline(r"N\to T")
        + " but it decreases with "
        + math_inline(r"k\to N/2")
        + ". The number of paths "
        + math_inline(r"\varphi[N,k]")
        + " increases with "
        + math_inline(r"N\to T")
        + " and with "
        + math_inline(r"k\to N/2")
        + ". In the limit, the largest number of paths is achieved by setting "
        + math_inline(r"N=T")
        + " and "
        + math_inline(r"k=N/2=T/2")
        + ", at the expense of training the classifier on only half of the data for each combination "
        + math_inline(r"(\theta=1/2)")
        + ".</p>"
    )


def chapter_12_examples_html() -> str:
    return (
        "<p>For "
        + math_inline("k=1")
        + ", we will obtain "
        + math_inline(r"\varphi[N,1]=1")
        + " path, in which case CPCV reduces to CV. Thus, CPCV can be understood as a generalization of CV for "
        + math_inline("k>1")
        + ".</p>"
        "<p>For "
        + math_inline("k=2")
        + ", we will obtain "
        + math_inline(r"\varphi[N,2]=N-1")
        + " paths. This is a particularly interesting case, because while training the classifier on a large "
        "portion of the data, "
        + math_inline(r"\theta=1-\frac{2}{N}")
        + ", we can generate almost as many backtest paths as the number of groups, "
        + math_inline("N-1")
        + ". An easy rule of thumb is to partition the data into "
        + math_inline(r"N=\varphi+1")
        + " groups, where "
        + math_inline(r"\varphi")
        + " is the number of paths we target, and then form "
        + math_inline(r"\binom{N}{N-2}")
        + " combinations. In the limit, we can assign one group per observation, "
        + math_inline("N=T")
        + ", and generate "
        + math_inline(r"\varphi[T,2]=T-1")
        + " paths, while training the classifier on a portion "
        + math_inline(r"\theta=1-\frac{2}{T}")
        + " of the data per combination.</p>"
    )


def chapter_12_overfitting_intro_html() -> str:
    return (
        "<p>Given a sample of IID random variables, "
        + math_inline(r"x_i\sim Z,\ i=1,\ldots,I")
        + ", where "
        + math_inline("Z")
        + " is the standard Normal distribution, the expected maximum of that sample can be approximated as</p>"
        + math_display(
            r"\mathbb{E}[\max\{x_i\}_{i=1,\ldots,I}]"
            r"\approx(1-\gamma)Z^{-1}\!\left[1-\frac{1}{I}\right]"
            r"+\gamma Z^{-1}\!\left[1-\frac{e^{-1}}{I}\right]"
            r"\le\sqrt{2\log[I]}."
        )
    )


def chapter_12_overfitting_where_html() -> str:
    return (
        "<p>where "
        + math_inline(r"Z^{-1}[\cdot]")
        + " is the inverse of the CDF of "
        + math_inline("Z")
        + ", "
        + math_inline(r"\gamma\approx0.5772156649\cdots")
        + " is the Euler-Mascheroni constant, and "
        + math_inline(r"I\gg1")
        + " (see Bailey et al. [2014] for a proof). Now suppose that a researcher backtests "
        + math_inline("I")
        + " strategies on an instrument that behaves like a martingale, with Sharpe ratios "
        + math_inline(r"\{y_i\}_{i=1,\ldots,I}")
        + ", "
        + math_inline(r"\mathbb{E}[y_i]=0")
        + ", "
        + math_inline(r"\sigma^2[y_i]>0")
        + ", and "
        + math_inline(r"\frac{y_i}{\sigma[y_i]}\sim Z")
        + ". Even though the true Sharpe ratio is zero, we expect to find one strategy with a Sharpe ratio of</p>"
        + math_display(
            r"\mathbb{E}[\max\{y_i\}_{i=1,\ldots,I}]"
            r"=\mathbb{E}[\max\{x_i\}_{i=1,\ldots,I}]\sigma[y_i]."
        )
    )


def chapter_12_wf_variance_html() -> str:
    return (
        "<p>WF backtests exhibit high variance, "
        + math_inline(r"\sigma[y_i]\gg0")
        + ", for at least one reason: A large portion of the decisions are based on a small portion of the dataset. "
        "A few observations will have a large weight on the Sharpe ratio. Using a warm-up period will reduce the "
        "backtest length, which may contribute to making the variance even higher. WF's high variance leads to "
        "false discoveries, because researchers will select the backtest with the maximum estimated Sharpe ratio, "
        "even if the true Sharpe ratio is zero. That is the reason it is imperative to control for the number of "
        "trials "
        + math_inline("I")
        + " in the context of WF backtesting. Without this information, it is not possible to determine the "
        "Family-Wise Error Rate (FWER), False Discovery Rate (FDR), Probability of Backtest Overfitting (PBO, "
        "see Chapter 11) or similar model assessment statistic.</p>"
        "<p>CV backtests (Section 12.3) address that source of variance by training each classifier on equal and "
        "large portions of the dataset. Although CV leads to fewer false discoveries than WF, both approaches still "
        "estimate the Sharpe ratio from a single path for a strategy "
        + math_inline("i")
        + ", "
        + math_inline("y_i")
        + ", and that estimation may be highly volatile. In contrast, CPCV derives the distribution of Sharpe "
        "ratios from a large number of paths, "
        + math_inline(r"j=1,\ldots,\varphi")
        + ", with mean "
        + math_inline(r"\mathbb{E}[\{y_{i,j}\}_{j=1,\ldots,\varphi}]=\mu_i")
        + " and variance "
        + math_inline(r"\sigma^2[\{y_{i,j}\}_{j=1,\ldots,\varphi}]=\sigma_i^2")
        + ". The variance of the sample mean of CPCV paths is</p>"
        + math_display(
            r"\sigma^2[\mu_i]=\varphi^{-2}\left(\varphi\sigma_i^2"
            r"+\varphi(\varphi-1)\sigma_i^2\bar\rho_i\right)"
            r"=\varphi^{-1}\sigma_i^2\left(1+(\varphi-1)\bar\rho_i\right)."
        )
    )


def chapter_12_variance_tail_html() -> str:
    return (
        "<p>where "
        + math_inline(r"\sigma_i^2")
        + " is the variance of the Sharpe ratios across paths for strategy "
        + math_inline("i")
        + ", and "
        + math_inline(r"\bar\rho_i")
        + " is the average off-diagonal correlation among "
        + math_inline(r"\{y_{i,j}\}_{j=1,\ldots,\varphi}")
        + ". CPCV leads to fewer false discoveries than CV and WF, because "
        + math_inline(r"\bar\rho_i<1")
        + " implies that the variance of the sample mean is lower than the variance of the sample,</p>"
        + math_display(r"\varphi^{-1}\sigma_i^2\le\sigma^2[\mu_i]<\sigma_i^2.")
    )


def chapter_12_final_html() -> str:
    return (
        "<p>The more uncorrelated the paths are, "
        + math_inline(r"\bar\rho_i\ll1")
        + ", the lower CPCV's variance will be, and in the limit CPCV will report the true Sharpe ratio "
        + math_inline(r"\mathbb{E}[y_i]")
        + " with zero variance, "
        + math_inline(r"\lim_{\varphi\to\infty}\sigma^2[\mu_i]=0")
        + ". There will not be selection bias, because the strategy selected out of "
        + math_inline(r"i=1,\ldots,I")
        + " will be the one with the highest true Sharpe ratio.</p>"
        "<p>Of course, we know that zero variance is unachievable, since "
        + math_inline(r"\varphi")
        + " has an upper bound, "
        + math_inline(r"\varphi\le\varphi[T,T/2]")
        + ". Still, for a large enough number of paths "
        + math_inline(r"\varphi")
        + ", CPCV could make the variance of the backtest so small as to make the probability of a false discovery "
        "negligible.</p>"
        "<p>In Chapter 11, we argued that backtest overfitting may be the most important open problem in all of "
        "mathematical finance. Let us see how CPCV helps address this problem in practice. Suppose that a researcher "
        "submits a strategy to a journal, supported by an overfit WF backtest, selected from a large number of "
        "undisclosed trials. The journal could ask the researcher to repeat his experiments using a CPCV for a given "
        + math_inline("N")
        + " and "
        + math_inline("k")
        + ". Because the researcher did not know in advance the number and characteristics of the paths to be "
        "backtested, his overfitting efforts will be easily defeated. The paper will be rejected or withdrawn from "
        "consideration. Hopefully CPCV will be used to reduce the number of false discoveries published in journals "
        "and elsewhere.</p>"
    )


def chapter_12_algorithm_list_html() -> str:
    return (
        '<ol class="algorithm-list">'
        "<li>Partition "
        + math_inline("T")
        + " observations into "
        + math_inline("N")
        + " groups without shuffling, where groups "
        + math_inline(r"n=1,\ldots,N-1")
        + " are of size "
        + math_inline(r"\lfloor T/N\rfloor")
        + ", and the "
        + math_inline("N")
        + "th group is of size "
        + math_inline(r"T-\lfloor T/N\rfloor(N-1)")
        + ".</li>"
        "<li>Compute all possible training/testing splits, where for each split "
        + math_inline("N-k")
        + " groups constitute the training set and "
        + math_inline("k")
        + " groups constitute the testing set.</li>"
        "<li>For any pair of labels "
        + math_inline(r"(y_i,y_j)")
        + ", where "
        + math_inline("y_i")
        + " belongs to the training set and "
        + math_inline("y_j")
        + " belongs to the testing set, apply the <code>PurgedKFold</code> class to purge "
        + math_inline("y_i")
        + " if "
        + math_inline("y_i")
        + " spans over a period used to determine label "
        + math_inline("y_j")
        + ". This class will also apply an embargo, should some testing samples predate some training samples.</li>"
        "<li>Fit classifiers on the "
        + math_inline(r"\binom{N}{N-k}")
        + " training sets, and produce forecasts on the respective "
        + math_inline(r"\binom{N}{N-k}")
        + " testing sets.</li>"
        "<li>Compute the "
        + math_inline(r"\varphi[N,k]")
        + " backtest paths. You can calculate one Sharpe ratio from each path, and from that derive the empirical "
        "distribution of the strategy's Sharpe ratio, rather than a single Sharpe ratio like WF or CV.</li>"
        "</ol>"
    )


def chapter_12_paragraph_html(text: str) -> str | None:
    stripped = text.strip()
    if stripped.startswith("WF suffers from three major disadvantages"):
        return chapter_12_wf_pitfalls_html()
    if stripped.startswith("t which is only") or stripped.startswith("which is only a 34"):
        return ""
    if stripped.startswith("Investors often ask how"):
        return chapter_12_cv_intro_html()
    if stripped.startswith("the China scare of"):
        return ""
    if stripped in {"Advantages", "Disadvantages"}:
        return f'<p class="example-caption"><strong>{html.escape(stripped)}</strong></p>'
    if stripped.startswith("In this section I will present"):
        return (
            "<p>In this section I will present a new method, which addresses the main drawback of the WF and CV "
            "methods, namely that those schemes test a single path. I call it the “combinatorial purged "
            "cross-validation” (CPCV) method. Given a number "
            + math_inline(r"\varphi")
            + " of backtest paths targeted by the researcher, CPCV generates the precise number of combinations "
            "of training/testing sets needed to generate those paths, while purging training observations that "
            "contain leaked information.</p>"
        )
    if stripped.startswith("S1 S2 S3 S4 S5 S6") or stripped == "=":
        return ""
    if stripped.startswith("Consider T observations partitioned"):
        return chapter_12_combinatorial_splits_html()
    if stripped.startswith("Since each combination involves"):
        return chapter_12_paths_formula_html()
    if stripped.startswith("Figure 12.1 illustrates"):
        return chapter_12_figure_explanation_html()
    if stripped.startswith("(G3, S2)"):
        return chapter_12_path_examples_html()
    if stripped.startswith("For k = 1"):
        return chapter_12_examples_html()
    if stripped.startswith("If even more paths are needed"):
        return (
            "<p>If even more paths are needed, we can increase "
            + math_inline(r"k\to N/2")
            + ", but as explained earlier that will come at the cost of using a smaller portion of the dataset "
            "for training. In practice, "
            + math_inline("k=2")
            + " is often enough to generate the needed "
            + math_inline(r"\varphi")
            + " paths, by setting "
            + math_inline(r"N=\varphi+1\le T")
            + ".</p>"
        )
    if stripped == "ADDRESSES BACKTEST OVERFITTING":
        return ""
    if stripped.startswith("Given a sample of IID"):
        return chapter_12_overfitting_intro_html()
    if stripped == "I I":
        return ""
    if stripped.startswith("where Z"):
        return chapter_12_overfitting_where_html()
    if stripped.startswith("WF backtests exhibit"):
        return chapter_12_wf_variance_html()
    if stripped.startswith("where") and "off-diagonal correlation" in stripped:
        return chapter_12_variance_tail_html()
    if stripped.startswith("discoveries than CV and WF"):
        return ""
    if stripped.startswith("The more uncorrelated"):
        return chapter_12_final_html()
    fixed = chapter_12_text_html(stripped)
    if fixed != mathify_general_text(stripped):
        return f"<p>{fixed}</p>"
    return None


def chapter_12_block_figure_html(block: Block) -> str | None:
    if block.caption.startswith("Figure 12.1"):
        return chapter_12_figure_html("12.1")
    if block.caption.startswith("Figure 12.2"):
        return chapter_12_figure_html("12.2")
    return None


CHAPTER_13_FIGURE_PARAMS = [
    (0, 5),
    (0, 10),
    (0, 25),
    (0, 50),
    (0, 100),
    (5, 5),
    (5, 10),
    (5, 25),
    (5, 50),
    (5, 100),
    (10, 5),
    (10, 10),
    (10, 25),
    (10, 50),
    (10, 100),
    (-5, 5),
    (-5, 10),
    (-5, 25),
    (-5, 50),
    (-5, 100),
    (-10, 5),
    (-10, 10),
    (-10, 25),
    (-10, 50),
    (-10, 100),
]


def chapter_13_param_tex(forecast: int, half_life: int) -> str:
    return rf"\{{\mathbb{{E}}_0[P_{{i,T_i}}],\tau,\sigma\}}=\{{{forecast},{half_life},1\}}"


def chapter_13_figure_html(number: int) -> str:
    forecast, half_life = CHAPTER_13_FIGURE_PARAMS[number - 1]
    caption = (
        f"Figure 13.{number}: Heat-map for "
        + math_inline(chapter_13_param_tex(forecast, half_life))
    )
    alt = f"Figure 13.{number}: heat-map for forecast {forecast}, half-life {half_life}, sigma 1"
    return (
        '<figure class="book-figure heatmap-figure">'
        f'<img src="media/chapter-13-figure-13-{number}.png" alt="{html.escape(alt)}">'
        f"<figcaption>{caption}</figcaption></figure>"
    )


def table_13_1_html() -> str:
    rows = []
    for index, (forecast, half_life) in enumerate(CHAPTER_13_FIGURE_PARAMS, start=1):
        rows.append(
            "<tr>"
            f'<th scope="row">13.{index}</th>'
            f"<td>{forecast}</td>"
            f"<td>{half_life}</td>"
            "<td>1</td>"
            "<td>100</td>"
            "</tr>"
        )
    return (
        '<table class="semantic-table chapter-13-inputs">'
        "<thead><tr><th>Figure</th><th>Forecast</th><th>Half-Life</th><th>Sigma</th><th>maxHP</th></tr></thead>"
        "<tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def chapter_13_display_13_1() -> str:
    return math_display(
        r"\begin{aligned}"
        r"R^*&=\arg\max_{R\in\Omega}\{\operatorname{SR}_R\}\\"
        r"\operatorname{SR}_R&=\frac{\mathbb{E}[\pi_{i,T_i}\mid R]}{\sigma[\pi_{i,T_i}\mid R]}"
        r"\end{aligned}\qquad(13.1)"
    )


def chapter_13_definition_2_html() -> str:
    return (
        '<p class="definition-block"><strong>Definition 2: Overfit Trading Rule:</strong> '
        + math_inline("R^*")
        + " is overfit if</p>"
        + math_display(
            r"\mathbb{E}\left[\frac{\mathbb{E}[\pi_{j,T_j}\mid R^*]}{\sigma[\pi_{j,T_j}\mid R^*]}\right]"
            r"<\operatorname{Me}_{\Omega}\left["
            r"\mathbb{E}\left[\frac{\mathbb{E}[\pi_{j,T_j}\mid R]}{\sigma[\pi_{j,T_j}\mid R]}\right]"
            r"\right]"
        )
        + "<p>where "
        + math_inline(r"j=I+1,\ldots,J")
        + " and "
        + math_inline(r"\operatorname{Me}_{\Omega}[\cdot]")
        + " is the median.</p>"
    )


def chapter_13_algorithm_html() -> str:
    return (
        "<p>The algorithm consists of five sequential steps.</p>"
        '<ol class="algorithm-list">'
        "<li><p>Estimate the input parameters "
        + math_inline(r"\{\sigma,\varphi\}")
        + " by linearizing equation (13.2) as</p>"
        + math_display(
            r"P_{i,t}=\mathbb{E}_0[P_{i,T_i}]+\varphi(P_{i,t-1}-\mathbb{E}_0[P_{i,T_i}])+\xi_t\qquad(13.5)"
        )
        + "<p>Then form vectors "
        + math_inline("X")
        + ", "
        + math_inline("Y")
        + ", and "
        + math_inline("Z")
        + " by sequencing opportunities:</p>"
        + math_display(
            r"\begin{aligned}"
            r"X&=\begin{bmatrix}"
            r"P_{0,0}-\mathbb{E}_0[P_{0,T_0}]\\"
            r"P_{0,1}-\mathbb{E}_0[P_{0,T_0}]\\"
            r"\vdots\\"
            r"P_{I,T-1}-\mathbb{E}_0[P_{I,T_I}]"
            r"\end{bmatrix},\quad "
            r"Y=\begin{bmatrix}P_{0,1}\\P_{0,2}\\\vdots\\P_{I,T}\end{bmatrix},\quad "
            r"Z=\begin{bmatrix}"
            r"\mathbb{E}_0[P_{0,T_0}]\\"
            r"\mathbb{E}_0[P_{0,T_0}]\\"
            r"\vdots\\"
            r"\mathbb{E}_0[P_{I,T_I}]"
            r"\end{bmatrix}."
            r"\end{aligned}\qquad(13.6)"
        )
        + "<p>Applying OLS on equation (13.5), estimate the original O-U parameters as</p>"
        + math_display(
            r"\begin{aligned}"
            r"\hat{\varphi}&=\frac{\operatorname{cov}[Y,X]}{\operatorname{cov}[X,X]}\\"
            r"\hat{\xi}_t&=Y-Z-\hat{\varphi}X\\"
            r"\hat{\sigma}&=\sqrt{\operatorname{cov}[\hat{\xi}_t,\hat{\xi}_t]}"
            r"\end{aligned}\qquad(13.7)"
        )
        + "<p>where "
        + math_inline(r"\operatorname{cov}[\cdot,\cdot]")
        + " is the covariance operator.</p></li>"
        "<li>Construct a mesh of stop-loss and profit-taking pairs, "
        + math_inline(r"(\underline{\pi},\bar{\pi})")
        + ". For example, the Cartesian product of "
        + math_inline(r"\underline{\pi}=\{-\frac{1}{2}\sigma,-\sigma,\ldots,-10\sigma\}")
        + " and "
        + math_inline(r"\bar{\pi}=\{\frac{1}{2}\sigma,\sigma,\ldots,10\sigma\}")
        + " gives 20 x 20 nodes, each an alternative trading rule "
        + math_inline(r"R\in\Omega")
        + ".</li>"
        "<li>Generate a large number of paths, for example 100,000, for "
        + math_inline(r"\pi_{i,t}")
        + " using the estimates "
        + math_inline(r"\{\hat{\sigma},\hat{\varphi}\}")
        + " and the observed initial conditions "
        + math_inline(r"\{P_{i,0},\mathbb{E}_0[P_{i,T_i}]\}")
        + ". A maximum holding period may be imposed as a vertical barrier, so a position exits even when "
        + math_inline(r"\underline{\pi}\le\pi_{i,100}\le\bar{\pi}")
        + ".</li>"
        "<li>Apply the simulated paths to each node of the "
        + math_inline(r"20\times20")
        + " mesh. For each node, apply stop-loss and profit-taking logic, obtain simulated values of "
        + math_inline(r"\pi_{i,T_i}")
        + ", and compute the Sharpe ratio in equation (13.1).</li>"
        "<li>Use the resulting surface in three ways: <strong>Step 5a:</strong> determine the optimal pair "
        + math_inline(r"(\underline{\pi},\bar{\pi})")
        + " for the input parameters and initial conditions "
        + math_inline(r"\{P_{i,0},\mathbb{E}_0[P_{i,T_i}]\}")
        + "; <strong>Step 5b:</strong> given a profit target "
        + math_inline(r"\bar{\pi}_i")
        + ", determine the optimal stop-loss "
        + math_inline(r"\underline{\pi}_i")
        + "; <strong>Step 5c:</strong> given a maximum stop-loss "
        + math_inline(r"\underline{\pi}_i")
        + ", determine the optimal profit-taking level "
        + math_inline(r"\bar{\pi}_i")
        + " within the stop-loss range.</li>"
        "</ol>"
        + chapter_11_footnote(
            3,
            "The trading rule "
            + math_inline("R")
            + " could be characterized as a function of the three barriers, instead of the horizontal ones. "
            "That change would merely add one more dimension to the mesh (20 x 20 x 20). In this chapter we do not consider that setting, because it would make the visualization of the method less intuitive.",
        )
    )


def chapter_13_paragraph_html(text: str) -> str | None:
    stripped = text.strip()
    if stripped.startswith(("Forecast=", "Stop-Loss", "Profit-Taking")):
        return ""
    if "\x02" in stripped or "⏐" in stripped:
        return ""
    if stripped in {
        "1 I would like to thank Professor Peter Carr (New York University) for his contributions to this chapter.",
        "2 The strategy may still be the result of backtest overfitting, but at least the trading rule would not have",
        "contributed to that problem.",
        "3 The trading rule R could be characterized as a function of the three barriers, instead of the horizontal",
        "ones. That change would have no impact on the procedure. It would merely add one more dimension to the mesh (20 × 20 × 20). In this chapter we do not consider that setting, because it would make the visualization of the method less intuitive.",
        "mi i,t",
        "j",
        "2j (13.4) j=0 j=0",
        "where cov [⋅, ⋅] is the covariance operator.",
        "(13.2) is 𝜏 = − log[𝜑] , with the requirement that 𝜑 ∈ (0, 1). From that result, we can",
        "determine the value of 𝜑 associated with a certain half-life 𝜏 as 𝜑 = 2 𝜏.",
    }:
        return ""
    if "⎢" in stripped or "⎥" in stripped or "⋯" in stripped:
        return ""
    if stripped.startswith("E ") and "Tj |R" in stripped:
        return ""
    if stripped.startswith("In this chapter we will study"):
        return (
            "<p>In this chapter we will study an alternative backtesting method, which uses history to generate "
            "a synthetic dataset with statistical characteristics estimated from the observed data. This will "
            "allow us to backtest a strategy on a large number of unseen, synthetic testing sets, hence reducing "
            "the likelihood that the strategy has been fit to a particular set of data points.<sup>1</sup> "
            "This is a very extensive subject, and in order to reach some depth we will focus on the backtesting "
            "of trading rules.</p>"
            + chapter_11_footnote(
                1,
                "I would like to thank Professor Peter Carr (New York University) for his contributions to this chapter.",
            )
        )
    if stripped.startswith("Investment strategies can be defined"):
        return (
            "<p>Investment strategies can be defined as algorithms that postulate the existence of a market "
            "inefficiency. Some strategies rely on econometric models to predict prices, using macroeconomic "
            "variables such as GDP or inflation; other strategies use fundamental and accounting information to "
            "price securities, or search for arbitrage-like opportunities in the pricing of derivatives products. "
            "For instance, suppose that financial intermediaries tend to sell off-the-run bonds two days before "
            "U.S. Treasury auctions, in order to raise the cash needed for buying the new paper. One could monetize "
            "that knowledge by selling off-the-run bonds three days before auctions. But how? Each investment "
            "strategy requires an implementation tactic, often referred to as trading rules.</p>"
            "<p>There are dozens of hedge fund styles, each running dozens of unique investment strategies. While "
            "strategies can be heterogeneous in nature, tactics are relatively homogeneous. Trading rules provide "
            "the algorithm that must be followed to enter and exit a position. For example, a position will be "
            "entered when the strategy's signal reaches a certain value. Conditions for exiting a position are "
            "often defined through thresholds for profit-taking and stop-losses. These entry and exit rules rely "
            "on parameters that are usually calibrated via historical simulations. This practice leads to backtest "
            "overfitting, because these parameters target specific in-sample observations, to the point that the "
            "investment strategy is so attached to the past that it becomes unfit for the future.</p>"
            "<p>An important clarification is that we are interested in the exit corridor conditions that maximize "
            "performance. In other words, the position already exists, and the question is how to exit it optimally. "
            "This is the dilemma often faced by execution traders, and it should not be mistaken with the "
            "determination of entry and exit thresholds for investing in a security. For a study of that alternative "
            "question, see, for example, Bertram [2009].</p>"
            "<p>Bailey et al. [2014, 2017] discuss the problem of backtest overfitting, and provide methods to "
            "determine to what extent a simulated performance may be inflated due to overfitting. While assessing "
            "the probability of backtest overfitting is useful for discarding superfluous investment strategies, "
            "it would be better to avoid the risk of overfitting, at least when calibrating a trading rule. In "
            "theory this can be accomplished by deriving the optimal parameters for the trading rule directly from "
            "the stochastic process that generates the data, rather than engaging in historical simulations. This "
            "is the approach we take in this chapter.</p>"
        )
    if stripped.startswith("reaches a certain value."):
        return ""
    if stripped.startswith("Suppose an investment strategy"):
        return (
            "<p>Suppose an investment strategy "
            + math_inline("S")
            + " invests in "
            + math_inline(r"i=1,\ldots,I")
            + " opportunities or bets. At each opportunity "
            + math_inline("i")
            + ", "
            + math_inline("S")
            + " takes a position of "
            + math_inline("m_i")
            + " units of security "
            + math_inline("X")
            + ", where "
            + math_inline(r"m_i\in(-\infty,\infty)")
            + ". The transaction that entered such opportunity was priced at "
            + math_inline(r"m_iP_{i,0}")
            + ", where "
            + math_inline(r"P_{i,0}")
            + " is the average price per unit. After "
            + math_inline("t")
            + " observed transactions, its mark-to-market value is "
            + math_inline(r"m_iP_{i,t}")
            + ", and the mark-to-market profit/loss is "
            + math_inline(r"\pi_{i,t}=m_i(P_{i,t}-P_{i,0})")
            + ". A standard trading rule exits opportunity "
            + math_inline("i")
            + " at "
            + math_inline(r"t=T_i")
            + " as soon as one of two conditions is verified:</p>"
        )
    if stripped.startswith("These thresholds are equivalent"):
        return (
            "<p>These thresholds are equivalent to the horizontal barriers discussed in Chapter 3. Because "
            + math_inline(r"\underline{\pi}<\bar{\pi}")
            + ", one and only one of the two exit conditions can trigger the exit from opportunity "
            + math_inline("i")
            + ". Assuming that opportunity "
            + math_inline("i")
            + " can be exited at "
            + math_inline("T_i")
            + ", its final profit/loss is "
            + math_inline(r"\pi_{i,T_i}")
            + ". At the onset of each opportunity, the goal is to realize an expected profit "
            + math_inline(r"\mathbb{E}_0[\pi_{i,T_i}]=m_i(\mathbb{E}_0[P_{i,T_i}]-P_{i,0})")
            + ", where "
            + math_inline(r"\mathbb{E}_0[P_{i,T_i}]")
            + " is the forecasted price and "
            + math_inline(r"P_{i,0}")
            + " is the entry level.</p>"
        )
    if stripped.startswith("be exited at Ti"):
        return ""
    if stripped.startswith("Definition 1: Trading Rule"):
        return (
            '<p class="definition-block"><strong>Definition 1: Trading Rule:</strong> A trading rule for strategy '
            + math_inline("S")
            + " is defined by the set of parameters "
            + math_inline(r"R:=\{\underline{\pi},\bar{\pi}\}")
            + ".</p>"
        )
    if stripped == "More formally:":
        return "<p>More formally:</p>" + chapter_13_display_13_1()
    if stripped.startswith("where E [.]"):
        return (
            "<p>where "
            + math_inline(r"\mathbb{E}[\cdot]")
            + " and "
            + math_inline(r"\sigma[\cdot]")
            + " are respectively the expected value and standard deviation of "
            + math_inline(r"\pi_{i,T_i}")
            + ", conditional on trading rule "
            + math_inline("R")
            + ", over "
            + math_inline(r"i=1,\ldots,I")
            + ". Equation (13.1) maximizes the Sharpe ratio of "
            + math_inline("S")
            + " over the space of alternative trading rules "
            + math_inline("R")
            + ". Because we count with two variables to maximize "
            + math_inline(r"\operatorname{SR}_R")
            + " over a sample of size "
            + math_inline("I")
            + ", it is easy to overfit "
            + math_inline("R")
            + ". A trivial overfit occurs when a pair "
            + math_inline(r"(\underline{\pi},\bar{\pi})")
            + " targets a few outliers. Bailey et al. [2017] provide a rigorous definition of backtest overfitting, "
            "which can be applied to our study of trading rules as follows.</p>"
            + chapter_13_definition_2_html()
        )
    if stripped.startswith(("few outliers.", "Definition 2:", "E πj", "MeΩ E", "Intuitively, an optimal in-sample")):
        if stripped.startswith("Intuitively, an optimal in-sample"):
            return (
                "<p>Intuitively, an optimal in-sample (IS, "
                + math_inline(r"i\in[1,I]")
                + ") trading rule "
                + math_inline("R^*")
                + " is overfit when it is expected to underperform the median of alternative trading rules "
                + math_inline(r"R\in\Omega")
                + " out-of-sample (OOS, "
                + math_inline(r"j\in[I+1,J]")
                + "). This is essentially the same definition used in Chapter 11 to derive PBO.</p>"
            )
        return ""
    if stripped.startswith("because R∗"):
        return (
            "<p>Bailey et al. [2014] argue that it is hard not to overfit a backtest, particularly when there are "
            "free variables able to target specific observations IS, or the number of elements in "
            + math_inline(r"\Omega")
            + " is large. A trading rule introduces such free variables, because "
            + math_inline("R^*")
            + " can be determined independently from "
            + math_inline("S")
            + ". The outcome is that the backtest profits from random noise IS, making "
            + math_inline("R^*")
            + " unfit for OOS opportunities. Those same authors show that overfitting leads to negative performance "
            "OOS when "
            + math_inline(r"\Delta\pi_{i,t}")
            + " exhibits serial dependence. While PBO provides a useful method to evaluate to what extent a backtest "
            "has been overfit, it would be convenient to avoid this problem in the first place.<sup>2</sup></p>"
            + chapter_11_footnote(
                2,
                "The strategy may still be the result of backtest overfitting, but at least the trading rule would not have contributed to that problem.",
            )
        )
    if stripped.startswith("Until now we have not characterized"):
        return (
            "<p>Until now we have not characterized the stochastic process from which observations "
            + math_inline(r"\pi_{i,t}")
            + " are drawn. We are interested in finding an optimal trading rule (OTR) for scenarios where "
            "overfitting would be most damaging, such as when "
            + math_inline(r"\pi_{i,t}")
            + " exhibits serial correlation. In particular, suppose a discrete Ornstein-Uhlenbeck (O-U) process on prices</p>"
            + math_display(
                r"P_{i,t}=(1-\varphi)\mathbb{E}_0[P_{i,T_i}]+\varphi P_{i,t-1}+\sigma\varepsilon_{i,t}\qquad(13.2)"
            )
        )
    if stripped.startswith("such that the random shocks"):
        return (
            "<p>such that the random shocks are IID distributed "
            + math_inline(r"\varepsilon_{i,t}\sim N(0,1)")
            + ". The seed value for this process is "
            + math_inline(r"P_{i,0}")
            + ", the level targeted by opportunity "
            + math_inline("i")
            + " is "
            + math_inline(r"\mathbb{E}_0[P_{i,T_i}]")
            + ", and "
            + math_inline(r"\varphi")
            + " determines the speed at which "
            + math_inline(r"P_{i,0}")
            + " converges toward "
            + math_inline(r"\mathbb{E}_0[P_{i,T_i}]")
            + ". Because "
            + math_inline(r"\pi_{i,t}=m_i(P_{i,t}-P_{i,0})")
            + ", equation (13.2) implies that opportunity performance is characterized by</p>"
            + math_display(
                r"\frac{1}{m_i}\pi_{i,t}=(1-\varphi)\mathbb{E}_0[P_{i,T_i}]-P_{i,0}+\varphi P_{i,t-1}+\sigma\varepsilon_{i,t}\qquad(13.3)"
            )
        )
    if stripped.startswith("From the proof to Proposition"):
        return (
            "<p>From the proof to Proposition 4 in Bailey and López de Prado [2013], the distribution of the process "
            "specified in equation (13.2) is Gaussian with parameters</p>"
            + math_display(
                r"\pi_{i,t}\sim N\left["
                r"m_i\left((1-\varphi)\mathbb{E}_0[P_{i,T_i}]\sum_{j=0}^{t-1}\varphi^j-P_{i,0}\right),"
                r"m_i^2\sigma^2\sum_{j=0}^{t-1}\varphi^{2j}"
                r"\right]\qquad(13.4)"
            )
        )
    if stripped.startswith("and a necessary and sufficient condition"):
        return (
            "<p>A necessary and sufficient condition for stationarity is "
            + math_inline(r"\varphi\in(-1,1)")
            + ". Given input parameters "
            + math_inline(r"\{\sigma,\varphi\}")
            + " and initial conditions "
            + math_inline(r"\{P_{i,0},\mathbb{E}_0[P_{i,T_i}]\}")
            + " associated with opportunity "
            + math_inline("i")
            + ", is there an OTR "
            + math_inline(r"R^*:=(\underline{\pi},\bar{\pi})")
            + "? Similarly, if strategy "
            + math_inline("S")
            + " predicts a profit target "
            + math_inline(r"\bar{\pi}")
            + ", can we compute the optimal stop-loss "
            + math_inline(r"\underline{\pi}")
            + " given "
            + math_inline(r"\{\sigma,\varphi\}")
            + "? If the answer is affirmative, no backtest is needed to determine "
            + math_inline("R^*")
            + ", thus avoiding overfitting the trading rule.</p>"
        )
    if stripped.startswith("The algorithm consists"):
        return chapter_13_algorithm_html()
    if stripped.startswith(("Step 1:", "We can then form vectors", "Applying OLS", "Step 2:", "Step 3:", "{P_{i,0}", "Step 5b:")):
        return ""
    if stripped.startswith("Bailey and López de Prado") and "half-life" in stripped:
        return (
            "<p>Bailey and López de Prado [2013] prove that the half-life of the process in equation (13.2) is "
            + math_inline(r"\tau=-\frac{\log[2]}{\log[\varphi]}")
            + ", with "
            + math_inline(r"\varphi\in(0,1)")
            + ". From that result, the value of "
            + math_inline(r"\varphi")
            + " associated with a half-life "
            + math_inline(r"\tau")
            + " is "
            + math_inline(r"\varphi=2^{-1/\tau}")
            + ".</p>"
        )
    if stripped.startswith("Snippet 13.1 provides"):
        return (
            "<p>Snippet 13.1 provides a Python implementation of the experiments conducted in this chapter. "
            "Function <code>main</code> produces a Cartesian product of parameters "
            + math_inline(r"(\mathbb{E}_0[P_{i,T_i}],\tau)")
            + ", which characterize the stochastic process from equation (13.5). Without loss of generality, all "
            "simulations use "
            + math_inline(r"\sigma=1")
            + ". Then, for each pair "
            + math_inline(r"(\mathbb{E}_0[P_{i,T_i}],\tau)")
            + ", function <code>batch</code> computes Sharpe ratios associated with various trading rules.</p>"
        )
    if stripped.startswith("Snippet 13.2 computes"):
        return (
            "<p>Snippet 13.2 computes a "
            + math_inline(r"20\times20")
            + " mesh of Sharpe ratios, one for each trading rule "
            + math_inline(r"(\underline{\pi},\bar{\pi})")
            + ", given a pair of parameters "
            + math_inline(r"(\mathbb{E}_0[P_{i,T_i}],\tau)")
            + ". The maximum holding period is set at 100. We fix "
            + math_inline(r"P_{i,0}=0")
            + ", since the distance "
            + math_inline(r"P_{i,t-1}-\mathbb{E}_0[P_{i,T_i}]")
            + " in equation (13.5) drives convergence, not absolute price levels. Once one of the three barriers is "
            "touched, the exit price is stored and the next iteration starts. After all iterations are completed, "
            "the Sharpe ratio is computed for that pair and the algorithm moves to the next pair.</p>"
        )
    if stripped.startswith("Table 13.1 lists"):
        return (
            "<p>Table 13.1 lists the combinations analyzed in this study. Although different values for these "
            "inputs would render different numerical results, the combinations applied allow us to analyze the most "
            "general cases. Column “Forecast” refers to "
            + math_inline(r"\mathbb{E}_0[P_{i,T_i}]")
            + "; column “Half-Life” refers to "
            + math_inline(r"\tau")
            + "; column “Sigma” refers to "
            + math_inline(r"\sigma")
            + "; column “maxHP” stands for maximum holding period.</p>"
        )
    if stripped.startswith("are represented in grayscale"):
        return (
            "<p>In the following figures, we have plotted the non-annualized Sharpe ratios that result from "
            "various combinations of profit-taking and stop-loss exit conditions. We have omitted the negative sign "
            "in the y-axis (stop-losses) for simplicity. Sharpe ratios are represented in grayscale, with lighter "
            "areas indicating better performance and darker areas indicating worse performance. Performance "
            + math_inline(r"(\pi_{i,T_i})")
            + " is computed per unit held "
            + math_inline(r"(m_i=1)")
            + ", since other values of "
            + math_inline("m_i")
            + " simply rescale performance with no impact on the Sharpe ratio.</p>"
        )
    if stripped.startswith("Cases with zero long-run"):
        return (
            "<p>Cases with zero long-run equilibrium are consistent with market-makers, who provide liquidity under "
            "the assumption that price deviations from current levels will correct themselves over time. The smaller "
            + math_inline(r"\tau")
            + ", the smaller is the autoregressive coefficient "
            + math_inline(r"(\varphi=2^{-1/\tau})")
            + ". A small autoregressive coefficient with zero expected profit means that most pairs "
            + math_inline(r"(\underline{\pi},\bar{\pi})")
            + " deliver zero performance.</p>"
        )
    if stripped.startswith("sive coefficient"):
        return (
            "<p>Figure 13.1 shows the heat-map for "
            + math_inline(chapter_13_param_tex(0, 5))
            + ". The half-life is so small that performance is maximized in a narrow range of small profit-taking "
            "with large stop-losses. The optimal trading rule is to hold inventory long enough for a small profit, "
            "even at the expense of experiencing 5-fold or 7-fold unrealized losses. Sharpe ratios are high, "
            "reaching levels of around 3.2.</p>"
        )
    if stripped.startswith("high, reaching"):
        return (
            "<p>This is in fact what many market-makers do in practice, and is consistent with the asymmetric payoff "
            "dilemma described in Easley et al. [2011]. The worst possible trading rule in this setting combines a "
            "short stop-loss with a large profit-taking threshold. Performance is closest to neutral in the diagonal "
            "of the mesh, where profit-taking and stop-losses are symmetric.</p>"
            "<p>Figure 13.2 shows that increasing "
            + math_inline(r"\tau")
            + " from 5 to 10 spreads the areas of highest and lowest performance over the mesh of pairs "
            + math_inline(r"(\underline{\pi},\bar{\pi})")
            + ", while Sharpe ratios decrease.</p>"
        )
    if stripped.startswith("autoregressive coefficient"):
        return (
            "<p>This happens because a larger half-life increases the magnitude of the autoregressive coefficient "
            + math_inline(r"(\varphi=2^{-1/\tau})")
            + ", bringing the process closer to a random walk. Figures 13.3, 13.4, and 13.5 continue that progression. "
            "Eventually, as "
            + math_inline(r"\varphi\to1")
            + ", there are no recognizable areas where performance can be maximized.</p>"
        )
    if stripped.startswith("prevents overfitting"):
        return (
            "<p>Calibrating a trading rule on a random walk through historical simulations would lead to backtest "
            "overfitting, because one random combination of profit-taking and stop-loss that happened to maximize "
            "Sharpe ratio would be selected. This is why backtesting on synthetic data matters: it prevents "
            "overfitting by recognizing when performance exhibits no consistent pattern, indicating that there is no "
            "optimal trading rule.</p>"
        )
    if stripped.startswith("Cases with positive long-run"):
        return (
            "<p>Cases with positive long-run equilibrium are consistent with the business of a position-taker, such "
            "as a hedge fund or asset manager. Figure 13.6 shows the results for "
            + math_inline(chapter_13_param_tex(5, 5))
            + ". Because positions tend to make money, the optimal profit-taking is higher than in the zero-equilibrium "
            "case, centered around 6, with stop-losses between 4 and 10. The optimal region takes a rectangular shape, "
            "combining a wide stop-loss range with a narrower profit-taking range. Performance is highest across all "
            "experiments, with Sharpe ratios around 12.</p>"
            "<p>Figure 13.7 increases the half-life from "
            + math_inline(r"\tau=5")
            + " to "
            + math_inline(r"\tau=10")
            + ". The optimal profit-taking is centered around 5, with stop-losses between 7 and 10. Figure 13.8 sets "
            + math_inline(r"\tau=25")
            + ", where optimal profit-taking centers around 3 and stop-losses range between 9 and 10.</p>"
        )
    if stripped.startswith("area of optimal performance"):
        return (
            "<p>The previous squared area of optimal performance gives way to a semi-circle of small profit-taking "
            "with large stop-loss thresholds. Figure 13.9 raises the half-life to "
            + math_inline(r"\tau=50")
            + ", spreading the optimal region while Sharpe ratios fall to 0.8. Figure 13.10 sets "
            + math_inline(r"\tau=100")
            + ", making the process so close to a random walk that the maximum Sharpe ratio is only 0.32. A similar "
            "pattern appears in Figures 13.11 through 13.15, where "
            + math_inline(r"\mathbb{E}_0[P_{i,T_i}]=10")
            + " and "
            + math_inline(r"\tau")
            + " increases from 5 to 100.</p>"
            + "".join(chapter_13_figure_html(number) for number in range(9, 16))
        )
    if stripped.startswith("A rational market participant"):
        return (
            "<p>A rational market participant would not initiate a position under the assumption that a loss is the "
            "expected outcome. However, if a trader recognizes that losses are the expected outcome of a pre-existing "
            "position, she still needs a strategy to stop out of that position while minimizing losses. Figure 13.16 "
            "uses "
            + math_inline(chapter_13_param_tex(-5, 5))
            + ". Compared with Figure 13.6, it appears as a rotated complement: the profit in Figure 13.6 becomes a "
            "loss in Figure 13.16, and vice versa.</p>"
        )
    if stripped.startswith("appears as if one is"):
        return (
            "<p>One case is a reverse image of the other, just as a gambler's loss is the house's gain. As expected, "
            "Sharpe ratios are negative, with a worst performance region centered around the stop-loss of 6 and "
            "profit-taking thresholds between 4 and 10. In Figure 13.17, "
            + math_inline(r"\tau=10")
            + " and proximity to a random walk plays in our favor: the worst-performance region spreads out and "
            "performance becomes less negative, with Sharpe ratios around -9. Figures 13.18, 13.19, and 13.20 show "
            "the same progression as "
            + math_inline(r"\tau")
            + " rises to 25, 50, and 100. Figures 13.21 through 13.25 repeat the process for "
            + math_inline(r"\mathbb{E}_0[P_{i,T_i}]=-10")
            + ". The same rotated-complement pattern appears.</p>"
        )
    fixed = stripped.replace("datapoints", "data points").replace("marketmakers", "market-makers")
    if fixed != stripped:
        return f"<p>{mathify_general_text(fixed)}</p>"
    return None


def chapter_13_list_html(block: Block) -> str | None:
    if block.kind == "ulist" and block.lines and "profit-taking threshold" in block.lines[0]:
        return (
            "<ul>"
            "<li>"
            + math_inline(r"\pi_{i,T_i}\ge\bar{\pi}")
            + ", where "
            + math_inline(r"\bar{\pi}>0")
            + " is the profit-taking threshold.</li>"
            "<li>"
            + math_inline(r"\pi_{i,T_i}\le\underline{\pi}")
            + ", where "
            + math_inline(r"\underline{\pi}<0")
            + " is the stop-loss threshold.</li>"
            "</ul>"
        )
    if block.kind == "olist" and block.lines and block.lines[0].startswith("Define a set of alternative"):
        return (
            "<ol>"
            "<li>Define a set of alternative values of "
            + math_inline("R")
            + ", "
            + math_inline(r"\Omega:=\{R\}")
            + ".</li>"
            "<li>Simulate historically the performance of "
            + math_inline("S")
            + " under alternative values "
            + math_inline(r"R\in\Omega")
            + ".</li>"
            "<li>Select the optimal "
            + math_inline("R^*")
            + ".</li>"
            "</ol>"
        )
    return None


def chapter_13_table_html(block: Block) -> str | None:
    if block.caption.startswith("Table 13.1:"):
        return (
            '<figure class="table-figure"><figcaption>Table 13.1: Input Parameter Combinations Used in the Simulations</figcaption>'
            f'<div class="table-wrap">{table_13_1_html()}</div></figure>'
        )
    return None


def chapter_13_block_figure_html(block: Block) -> str | None:
    match = re.search(r"Figure 13\.(\d+):", block.caption)
    if not match:
        return None
    number = int(match.group(1))
    if 9 <= number <= 15:
        return ""
    if 1 <= number <= 25:
        return chapter_13_figure_html(number)
    return None


def chapter_14_footnote(number: int, content_html: str) -> str:
    return f'<p class="footnote"><sup>{number}</sup> {content_html}</p>'


def chapter_14_snippet_14_5_html() -> str:
    return (
        '<figure class="quote-snippet">'
        "<figcaption>Snippet 14.5: Marcos' Third Law of Backtesting. Most Discoveries in Finance Are False Because of Its Violation</figcaption>"
        "<blockquote>"
        "<p>Every backtest result must be reported in conjunction with all the trials involved in its production. "
        "Absent that information, it is impossible to assess the backtest's false discovery probability.</p>"
        "</blockquote>"
        '<p class="quote-attribution">Marcos López de Prado, <em>Advances in Financial Machine Learning</em> (2018)</p>'
        "</figure>"
    )


def chapter_14_figure_html(number: str) -> str:
    figures = {
        "14.1": (
            "media/afml-229_1.jpg",
            "Figure 14.1: Examples of drawdown (DD) and time under water + (TuW)",
        ),
        "14.2": (
            "media/afml-231_1.jpg",
            "Figure 14.2: PSR as a function of skewness and sample length",
        ),
        "14.3": (
            "media/afml-232_1.jpg",
            "Figure 14.3: "
            + math_inline("SR^*")
            + " as a function of "
            + math_inline(r"\mathbb{V}[\{\widehat{SR}_n\}]")
            + " and "
            + math_inline("N"),
        ),
    }
    src, caption = figures[number]
    alt = re.sub(r"<[^>]+>", "", caption)
    return f'<figure class="book-figure"><img src="{src}" alt="{html.escape(alt)}"><figcaption>{caption}</figcaption></figure>'


def chapter_14_twr_html() -> str:
    return (
        "<p>Total return is the rate of return from realized and unrealized gains and losses, including accrued "
        "interest, paid coupons, and dividends for the measurement period. GIPS rules calculate time-weighted "
        "rates of return (TWRR), adjusted for external cash flows (CFA Institute [2010]). Periodic and "
        "sub-periodic returns are geometrically linked. For periods beginning on or after January 1, 2005, "
        "GIPS rules mandate calculating portfolio returns that adjust for daily-weighted external cash flows. "
        "We can compute the TWRR by determining the value of the portfolio at the time of each external cash "
        "flow.<sup>2</sup> The TWRR for portfolio "
        + math_inline("i")
        + " between subperiods "
        + math_inline("[t-1,t]")
        + " is denoted "
        + math_inline("r_{i,t}")
        + ", with equations</p>"
        + math_display(
            r"\begin{aligned}"
            r"r_{i,t}&=\frac{\pi_{i,t}}{K_{i,t}}\\"
            r"\pi_{i,t}&=\sum_{j=1}^{J}\left[(\Delta P_{j,t}+A_{j,t})\theta_{i,j,t-1}"
            r"+\Delta\theta_{i,j,t}(\bar P_{j,t}-P_{j,t-1})\right]\\"
            r"K_{i,t}&=\sum_{j=1}^{J}\tilde P_{j,t-1}\theta_{i,j,t-1}"
            r"+\max\left\{0,\sum_{j=1}^{J}\bar{\tilde P}_{j,t}\Delta\theta_{i,j,t}\right\}."
            r"\end{aligned}"
        )
        + chapter_14_footnote(
            2,
            "External cash flows are assets (cash or investments) that enter or exit a portfolio. "
            "Dividend and interest income payments, for example, are not considered external cash flows.",
        )
    )


def chapter_14_cashflow_html() -> str:
    return (
        "<p>Cash inflows are assumed to occur at the beginning of the day, and cash outflows are assumed to occur "
        "at the end of the day. These sub-period returns are then linked geometrically as</p>"
        + math_display(r"\varphi_{i,T}=\prod_{t=1}^{T}(1+r_{i,t})")
        + "<p>The variable "
        + math_inline(r"\varphi_{i,T}")
        + " can be understood as the performance of one dollar invested in portfolio "
        + math_inline("i")
        + " over its entire life, "
        + math_inline(r"t=1,\ldots,T")
        + ". Finally, the annualized rate of return of portfolio "
        + math_inline("i")
        + " is</p>"
        + math_display(r"R_i=(\varphi_{i,T})^{1/y_i}-1")
        + "<p>where "
        + math_inline("y_i")
        + " is the number of years elapsed between "
        + math_inline("r_{i,1}")
        + " and "
        + math_inline("r_{i,T}")
        + ".</p>"
    )


def chapter_14_hhi_html() -> str:
    return (
        "<p>Given a time series of returns from bets, "
        + math_inline(r"\{r_t\}_{t=1,\ldots,T}")
        + ", we compute two weight series, "
        + math_inline("w^-")
        + " and "
        + math_inline("w^+")
        + ":</p>"
        + math_display(
            r"\begin{aligned}"
            r"r^+&=\{r_t\mid r_t\ge0\}_{t=1,\ldots,T},"
            r"&r^-&=\{r_t\mid r_t<0\}_{t=1,\ldots,T},\\"
            r"w^+&=\left\{r_t^+\left(\sum_t r_t^+\right)^{-1}\right\}_{t=1,\ldots,T},"
            r"&w^-&=\left\{r_t^-\left(\sum_t r_t^-\right)^{-1}\right\}_{t=1,\ldots,T}."
            r"\end{aligned}"
        )
        + "<p>Inspired by the Herfindahl-Hirschman Index (HHI), for "
        + math_inline(r"\lVert w^+\rVert>1")
        + ", where "
        + math_inline(r"\lVert\cdot\rVert")
        + " is the size of the vector, we define the concentration of positive returns as</p>"
        + math_display(
            r"\begin{aligned}"
            r"h^+&\equiv\frac{\sum_t(w_t^+)^2-\lVert w^+\rVert^{-1}}{1-\lVert w^+\rVert^{-1}}\\"
            r"&=\left(\frac{\mathbb{E}[(r_t^+)^2]}{\mathbb{E}[r_t^+]^2}-1\right)"
            r"(\lVert r^+\rVert-1)^{-1},"
            r"\end{aligned}"
        )
        + "<p>and the equivalent for concentration of negative returns, for "
        + math_inline(r"\lVert w^-\rVert>1")
        + ", as</p>"
        + math_display(
            r"\begin{aligned}"
            r"h^-&\equiv\frac{\sum_t(w_t^-)^2-\lVert w^-\rVert^{-1}}{1-\lVert w^-\rVert^{-1}}\\"
            r"&=\left(\frac{\mathbb{E}[(r_t^-)^2]}{\mathbb{E}[r_t^-]^2}-1\right)"
            r"(\lVert r^-\rVert-1)^{-1}."
            r"\end{aligned}"
        )
    )


def chapter_14_psr_html() -> str:
    return (
        "<p>The probabilistic Sharpe ratio (PSR) provides an adjusted estimate of SR, by removing the inflationary "
        "effect caused by short series with skewed and/or fat-tailed returns. Given a user-defined benchmark<sup>3</sup> "
        "Sharpe ratio "
        + math_inline("SR^*")
        + " and an observed Sharpe ratio "
        + math_inline(r"\widehat{SR}")
        + ", PSR estimates the probability that "
        + math_inline(r"\widehat{SR}")
        + " is greater than a hypothetical "
        + math_inline("SR^*")
        + ". Following Bailey and López de Prado [2012], PSR can be estimated as</p>"
        + math_display(
            r"\widehat{PSR}[SR^*]=Z\left["
            r"\frac{(\widehat{SR}-SR^*)\sqrt{T-1}}"
            r"{\sqrt{1-\hat{\gamma}_3\widehat{SR}+\frac{\hat{\gamma}_4-1}{4}\widehat{SR}^{2}}}"
            r"\right]"
        )
    )


def chapter_14_dsr_html() -> str:
    return (
        "<p>The deflated Sharpe ratio (DSR) is a PSR where the rejection threshold is adjusted to reflect the "
        "multiplicity of trials. Following Bailey and López de Prado [2014], DSR can be estimated as "
        + math_inline(r"\widehat{PSR}[SR^*]")
        + ", where the benchmark Sharpe ratio, "
        + math_inline("SR^*")
        + ", is no longer user-defined. Instead, "
        + math_inline("SR^*")
        + " is estimated as</p>"
        + math_display(
            r"SR^*=\sqrt{\mathbb{V}[\{\widehat{SR}_n\}]}\left("
            r"(1-\gamma)Z^{-1}\left[1-\frac{1}{N}\right]"
            r"+\gamma Z^{-1}\left[1-\frac{1}{N}e^{-1}\right]"
            r"\right)"
        )
    )


def chapter_14_paragraph_html(text: str) -> str | None:
    stripped = text.strip()
    if stripped.startswith("In the previous chapters, we have studied three backtesting paradigms"):
        return (
            "<p>In the previous chapters, we have studied three backtesting paradigms: First, historical simulations "
            "(the walk-forward method, Chapters 11 and 12). Second, scenario simulations (CV and CPCV methods, "
            "Chapter 12). Third, simulations on synthetic data (Chapter 13). Regardless of the backtesting paradigm "
            "you choose, you need to report the results according to a series of statistics that investors will use "
            "to compare and judge your strategy against competitors. In this chapter we will discuss some of the most "
            "commonly used performance evaluation statistics. Some of these statistics are included in the Global "
            "Investment Performance Standards (GIPS),<sup>1</sup> however a comprehensive analysis of performance "
            "requires metrics specific to the ML strategies under scrutiny.</p>"
            + chapter_14_footnote(
                1,
                'For further details, visit <a href="https://www.gipsstandards.org/">https://www.gipsstandards.org/</a>.',
            )
        )
    suppress_exact = {
        "1 For further details, visit https://www.gipsstandards.org.",
        "ri,t = Ki,t",
        "J",
        "j=1",
        "j=1 j=1",
        "T",
        "t=1",
        "SR =",
        "PSR ⎥",
        "SR ⎣ 4 ⎦",
        "∗",
        "N N",
    }
    if stripped in suppress_exact:
        return ""
    suppress_prefixes = (
        "test the strategy should be sufficiently long",
        "ment. For the purpose of computing this average",
        "ers a target risk-adjusted performance",
        "reported performance. If leverage takes place",
        "whether the strategy at times took dollar positions",
        "long positions. In long-short",
        "the backtest. A sequence of positions",
        "days a bet is held",
        "dollar amount traded per year",
        "trades, if every trade involves flipping",
        "subperiod t. The purpose of including",
        "2 External cash flows",
        "income payments, for example",
        "The variable 𝜑i,T",
        "where yi is the number",
        "⎪ t ⎪",
        "t wt t",
        "⎟ ⎝ ⎠",
        "and the equivalent for concentration",
        "ary on negative bet returns",
        "tHHI=getHHI",
        "fees, involved in one portfolio turnover",
        "formance (including brokerage fees",
        "where a is the average number",
        "formance relative to a benchmark",
        "by non-Normal returns or track record length",
        "standard significance level of 5%",
        "non-Normal returns, track record length",
        "PSR estimates the probability",
        "𝛾̂4 is the kurtosis",
        "tails (̂𝛾4 ). Figure 14.2",
        "where V[{SR",
        "involved in its production",
        "where TP is the number",
        "positives, TP precision",
        "of positive and negative cases",
    )
    if stripped.startswith(suppress_prefixes):
        return ""
    if stripped.startswith("Total return is the rate of return"):
        return chapter_14_twr_html()
    if stripped == "where":
        return "<p>where:</p>"
    if stripped.startswith("Cash inflows are assumed"):
        return chapter_14_cashflow_html()
    if stripped.startswith("Given a time series of returns from bets"):
        return chapter_14_hhi_html()
    if stripped.startswith("From Jensen’s inequality"):
        return (
            "<p>From Jensen's inequality, we know that "
            + math_inline(r"\mathbb{E}[r_t^+]^2\le\mathbb{E}[(r_t^+)^2]")
            + ". And because "
            + math_inline(r"\frac{\mathbb{E}[(r_t^+)^2]}{\mathbb{E}[r_t^+]^2}\le\lVert r^+\rVert")
            + ", we deduce that "
            + math_inline(r"\mathbb{E}[r_t^+]^2\le\mathbb{E}[(r_t^+)^2]\le\mathbb{E}[r_t^+]^2\lVert r^+\rVert")
            + ", with an equivalent boundary on negative bet returns. These definitions have a few interesting properties:</p>"
        )
    if stripped.startswith("It is easy to derive a similar expression"):
        return (
            "<p>It is easy to derive a similar expression for the concentration of bets across months, "
            + math_inline("h[t]")
            + ". Snippet 14.3 implements these concepts. Ideally, we are interested in strategies where bets' returns exhibit:</p>"
        )
    if stripped.startswith("Suppose that a strategy’s excess returns"):
        return (
            "<p>Suppose that a strategy's excess returns (in excess of the risk-free rate), "
            + math_inline(r"\{r_t\}_{t=1,\ldots,T}")
            + ", are IID Gaussian with mean "
            + math_inline(r"\mu")
            + " and variance "
            + math_inline(r"\sigma^2")
            + ". The Sharpe ratio (SR) is defined as</p>"
            + math_display(r"SR=\frac{\mu}{\sigma}")
        )
    if stripped.startswith("The purpose of SR is"):
        return (
            "<p>The purpose of SR is to evaluate the skills of a particular strategy or investor. Since "
            + math_inline(r"\mu")
            + " and "
            + math_inline(r"\sigma")
            + " are usually unknown, the true SR value cannot be known for certain. The inevitable consequence is "
            "that Sharpe ratio calculations may be the subject of substantial estimation errors.</p>"
        )
    if stripped.startswith("The probabilistic Sharpe ratio"):
        return chapter_14_psr_html()
    if stripped.startswith("where Z [.] is the cumulative"):
        return (
            "<p>where "
            + math_inline(r"Z[\cdot]")
            + " is the cumulative distribution function (CDF) of the standard Normal distribution, "
            + math_inline("T")
            + " is the number of observed returns, "
            + math_inline(r"\hat{\gamma}_3")
            + " is the skewness of the returns, and "
            + math_inline(r"\hat{\gamma}_4")
            + " is the kurtosis of the returns ("
            + math_inline(r"\hat{\gamma}_4=3")
            + " for Gaussian returns). For a given "
            + math_inline("SR^*")
            + ", PSR increases with greater "
            + math_inline(r"\widehat{SR}")
            + " (in the original sampling frequency, i.e. non-annualized), or longer track records ("
            + math_inline("T")
            + "), or positively skewed returns ("
            + math_inline(r"\hat{\gamma}_3")
            + "), but it decreases with fatter tails ("
            + math_inline(r"\hat{\gamma}_4")
            + ").</p>"
        )
    if stripped.startswith("3 This could be set"):
        return chapter_14_footnote(3, "This could be set to a default value of zero (i.e., comparing against no investment skill).")
    if stripped.startswith("The deflated Sharpe ratio"):
        return chapter_14_dsr_html()
    if stripped.startswith("The rationale behind DSR"):
        return (
            "<p>The rationale behind DSR is the following: Given a set of SR estimates, "
            + math_inline(r"\{\widehat{SR}_n\}")
            + ", its expected maximum is greater than zero, even if the true SR is zero. Under the null hypothesis "
            "that the actual Sharpe ratio is zero, "
            + math_inline(r"H_0:SR=0")
            + ", we know that the expected maximum "
            + math_inline(r"\widehat{SR}")
            + " can be estimated as "
            + math_inline("SR^*")
            + ". Indeed, "
            + math_inline("SR^*")
            + " increases quickly as more independent trials are attempted ("
            + math_inline("N")
            + "), or the trials involve a greater variance ("
            + math_inline(r"\mathbb{V}[\{\widehat{SR}_n\}]")
            + "). From this knowledge we derive the third law of backtesting.</p>"
        )
    if stripped.startswith("When all observed values are positive"):
        return (
            "<p>When all observed values are positive (label '1'), there are no true negatives or false positives, "
            "thus precision is 1, recall is a positive real number between 0 and 1 (inclusive), and accuracy equals "
            "recall. Then,</p>"
            + math_display(r"F_1=2\frac{\mathrm{recall}}{1+\mathrm{recall}}\ge\mathrm{recall}")
            + "<p>When all predicted values are positive (label '1'), there are no true negatives or false negatives, "
            "thus precision is a positive real number between 0 and 1 (inclusive), recall is 1, and accuracy equals "
            "precision. Then,</p>"
            + math_display(r"F_1=2\frac{\mathrm{precision}}{1+\mathrm{precision}}\ge\mathrm{precision}")
        )
    return None


def chapter_14_list_html(block: Block) -> str | None:
    first = block.lines[0] if block.lines else ""
    if block.kind == "ulist" and first.startswith("Time range:"):
        items = [
            "<strong>Time range:</strong> Time range specifies the start and end dates. The period used to test the strategy should be sufficiently long to include a comprehensive number of regimes (Bailey and López de Prado [2012]).",
            "<strong>Average AUM:</strong> This is the average dollar value of the assets under management. For the purpose of computing this average, the dollar value of long and short positions is considered to be a positive real number.",
            "<strong>Capacity:</strong> A strategy's capacity can be measured as the highest AUM that delivers a target risk-adjusted performance. A minimum AUM is needed to ensure proper bet sizing (Chapter 10) and risk diversification (Chapter 16). Beyond that minimum AUM, performance will decay as AUM increases, due to higher transaction costs and lower turnover.",
            "<strong>Leverage:</strong> Leverage measures the amount of borrowing needed to achieve the reported performance. If leverage takes place, costs must be assigned to it. One way to measure leverage is as the ratio of average dollar position size to average AUM.",
            "<strong>Maximum dollar position size:</strong> Maximum dollar position size informs us whether the strategy at times took dollar positions that greatly exceeded the average AUM. In general we will prefer strategies that take maximum dollar positions close to the average AUM, indicating that they do not rely on the occurrence of extreme events (possibly outliers).",
            "<strong>Ratio of longs:</strong> The ratio of longs shows what proportion of the bets involved long positions. In long-short, market neutral strategies, ideally this value is close to 0.5. If not, the strategy may have a position bias, or the backtested period may be too short and unrepresentative of future market conditions.",
            "<strong>Frequency of bets:</strong> The frequency of bets is the number of bets per year in the backtest. A sequence of positions on the same side is considered part of the same bet. A bet ends when the position is flattened or flipped to the opposite side. The number of bets is always smaller than the number of trades. A trade count would overestimate the number of independent opportunities discovered by the strategy.",
            "<strong>Average holding period:</strong> The average holding period is the average number of days a bet is held. High-frequency strategies may hold a position for a fraction of seconds, whereas low frequency strategies may hold a position for months or even years. Short holding periods may limit the capacity of the strategy. The holding period is related but different to the frequency of bets. For example, a strategy may place bets on a monthly basis, around the release of nonfarm payrolls data, where each bet is held for only a few minutes.",
            "<strong>Annualized turnover:</strong> Annualized turnover measures the ratio of the average dollar amount traded per year to the average annual AUM. High turnover may occur even with a low number of bets, as the strategy may require constant tuning of the position. High turnover may also occur with a low number of trades, if every trade involves flipping the position between maximum long and maximum short.",
            "<strong>Correlation to underlying:</strong> This is the correlation between strategy returns and the returns of the underlying investment universe. When the correlation is significantly positive or negative, the strategy is essentially holding or short-selling the investment universe, without adding much value.",
        ]
        return "<ul>" + "".join(f"<li>{item}</li>" for item in items) + "</ul>"
    if block.kind == "ulist" and first.startswith(
        (
            "Average AUM:",
            "Capacity:",
            "Leverage:",
            "Maximum dollar position size:",
            "Ratio of longs:",
            "Frequency of bets:",
            "Average holding period:",
            "Annualized turnover:",
            "Correlation to underlying:",
        )
    ):
        return ""
    if block.kind == "ulist" and first.startswith("PnL:"):
        items = [
            "<strong>PnL:</strong> The total amount of dollars (or the equivalent in the currency of denomination) generated over the entirety of the backtest, including liquidation costs from the terminal position.",
            "<strong>PnL from long positions:</strong> The portion of the PnL dollars that was generated exclusively by long positions. This is an interesting value for assessing the bias of long-short, market neutral strategies.",
            "<strong>Annualized rate of return:</strong> The time-weighted average annual rate of total return, including dividends, coupons, costs, etc.",
            "<strong>Hit ratio:</strong> The fraction of bets that resulted in a positive PnL.",
            "<strong>Average return from hits:</strong> The average return from bets that generated a profit.",
            "<strong>Average return from misses:</strong> The average return from bets that generated a loss.",
        ]
        return "<ul>" + "".join(f"<li>{item}</li>" for item in items) + "</ul>"
    if block.kind == "ulist" and first.startswith("𝜋i,t is the mark-to-market"):
        items = [
            math_inline(r"\pi_{i,t}") + " is the mark-to-market (MtM) profit or loss for portfolio " + math_inline("i") + " at time " + math_inline("t") + ".",
            math_inline("K_{i,t}") + " is the market value of the assets under management by portfolio " + math_inline("i") + " through subperiod " + math_inline("t") + ". The purpose of including the " + math_inline(r"\max\{\cdot\}") + " term is to fund additional purchases (ramp-up).",
            math_inline("A_{j,t}") + " is the interest accrued or dividend paid by one unit of instrument " + math_inline("j") + " at time " + math_inline("t") + ".",
            math_inline("P_{j,t}") + " is the clean price of security " + math_inline("j") + " at time " + math_inline("t") + ".",
            math_inline(r"\theta_{i,j,t}") + " are the holdings of portfolio " + math_inline("i") + " on security " + math_inline("j") + " at time " + math_inline("t") + ".",
            math_inline(r"\tilde P_{j,t}") + " is the dirty price of security " + math_inline("j") + " at time " + math_inline("t") + ".",
            math_inline(r"\bar P_{j,t}") + " is the average transacted clean price of portfolio " + math_inline("i") + " on security " + math_inline("j") + " over subperiod " + math_inline("t") + ".",
            math_inline(r"\bar{\tilde P}_{j,t}") + " is the average transacted dirty price of portfolio " + math_inline("i") + " on security " + math_inline("j") + " over subperiod " + math_inline("t") + ".",
        ]
        return "<ul>" + "".join(f"<li>{item}</li>" for item in items) + "</ul>"
    if block.kind == "ulist" and first.startswith("Aj,t is the interest"):
        return ""
    if block.kind == "olist" and first.startswith("0 ≤ h+"):
        return (
            "<ol>"
            "<li>" + math_inline(r"0\le h^+\le1") + ".</li>"
            "<li>" + math_inline(r"h^+=0\Leftrightarrow w_t^+=\lVert w^+\rVert^{-1},\ \forall t") + " (uniform returns).</li>"
            "<li>" + math_inline(r"h^+=1\Leftrightarrow \exists i\mid w_i^+=\sum_t w_t^+") + " (only one non-zero return).</li>"
            "</ol>"
        )
    if block.kind == "olist" and first.startswith("h+ = 1"):
        return ""
    if block.kind == "ulist" and first.startswith("high Sharpe ratio"):
        items = [
            "high Sharpe ratio",
            "high number of bets per year, " + math_inline(r"\lVert r^+\rVert+\lVert r^-\rVert=T"),
            "high hit ratio (relatively low " + math_inline(r"\lVert r^-\rVert") + ")",
            "low " + math_inline("h^+") + " (no right fat-tail)",
            "low " + math_inline("h^-") + " (no left fat-tail)",
            "low " + math_inline("h[t]") + " (bets are not concentrated in time)",
        ]
        return "<ul>" + "".join(f"<li>{item}</li>" for item in items) + "</ul>"
    if block.kind == "ulist" and first.startswith("HHI index on positive returns"):
        items = [
            "HHI index on positive returns: This is <code>getHHI(ret[ret&gt;=0])</code> in Snippet 14.3.",
            "HHI index on negative returns: This is <code>getHHI(ret[ret&lt;0])</code> in Snippet 14.3.",
            "HHI index on time between bets: This is <code>getHHI(ret.groupby(pd.TimeGrouper(freq='M')).count())</code> in Snippet 14.3.",
            "95-percentile DD: This is the 95th percentile of the DD series derived by Snippet 14.4.",
            "95-percentile TuW: This is the 95th percentile of the TuW series derived by Snippet 14.4.",
        ]
        return "<ul>" + "".join(f"<li>{item}</li>" for item in items) + "</ul>"
    if block.kind == "ulist" and first.startswith("HHI index on negative returns"):
        return ""
    if block.kind == "ulist" and first.startswith("Broker fees per turnover"):
        items = [
            "<strong>Broker fees per turnover:</strong> These are the fees paid to the broker for turning the portfolio over, including exchange fees.",
            "<strong>Average slippage per turnover:</strong> These are execution costs, excluding broker fees, involved in one portfolio turnover. For example, it includes the loss caused by buying a security at a fill-price higher than the mid-price at the moment the order was sent to the execution broker.",
            "<strong>Dollar performance per turnover:</strong> This is the ratio between dollar performance (including brokerage fees and slippage costs) and total portfolio turnovers. It signifies how much costlier the execution could become before the strategy breaks even.",
            "<strong>Return on execution costs:</strong> This is the ratio between dollar performance (including brokerage fees and slippage costs) and total execution costs. It should be a large multiple, to ensure that the strategy will survive worse-than-expected execution.",
        ]
        return "<ul>" + "".join(f"<li>{item}</li>" for item in items) + "</ul>"
    if block.kind == "ulist" and first.startswith(("Dollar performance per turnover", "Return on execution costs")):
        return ""
    if block.kind == "ulist" and first.startswith("Annualized Sharpe ratio"):
        items = [
            "<strong>Annualized Sharpe ratio:</strong> This is the SR value, annualized by a factor " + math_inline(r"\sqrt a") + ", where " + math_inline("a") + " is the average number of returns observed per year. This common annualization method relies on the assumption that returns are IID.",
            "<strong>Information ratio:</strong> This is the SR equivalent of a portfolio that measures its performance relative to a benchmark. It is the annualized ratio between the average excess return and the tracking error. The excess return is measured as the portfolio's return in excess of the benchmark's return. The tracking error is estimated as the standard deviation of the excess returns.",
            "<strong>Probabilistic Sharpe ratio:</strong> PSR corrects SR for inflationary effects caused by non-Normal returns or track record length. It should exceed 0.95, for the standard significance level of 5%. It can be computed on absolute or relative returns.",
            "<strong>Deflated Sharpe ratio:</strong> DSR corrects SR for inflationary effects caused by non-Normal returns, track record length, and multiple testing/selection bias. It should exceed 0.95, for the standard significance level of 5%. It can be computed on absolute or relative returns.",
        ]
        return "<ul>" + "".join(f"<li>{item}</li>" for item in items) + "</ul>"
    if block.kind == "ulist" and first.startswith(("Information ratio:", "Probabilistic Sharpe ratio:", "Deflated Sharpe ratio:")):
        return ""
    if block.kind == "ulist" and first.startswith("Accuracy:"):
        items = [
            "<strong>Accuracy:</strong> Accuracy is the fraction of opportunities correctly labeled by the overlay algorithm,"
            + math_display(r"\mathrm{accuracy}=\frac{TP+TN}{TP+TN+FP+FN}")
            + "where <code>TP</code> is the number of true positives, <code>TN</code> is the number of true negatives, <code>FP</code> is the number of false positives, and <code>FN</code> is the number of false negatives.",
            "<strong>Precision:</strong> Precision is the fraction of true positives among the predicted positives,"
            + math_display(r"\mathrm{precision}=\frac{TP}{TP+FP}"),
            "<strong>Recall:</strong> Recall is the fraction of true positives among the positives,"
            + math_display(r"\mathrm{recall}=\frac{TP}{TP+FN}"),
            "<strong>F1:</strong> Accuracy may not be an adequate classification score for meta-labeling applications. Suppose that, after you apply meta-labeling, there are many more negative cases (label '0') than positive cases (label '1'). Under that scenario, a classifier that predicts every case to be negative will achieve high accuracy, even though recall is 0 and precision is undefined. The F1 score corrects for that flaw, by assessing the classifier in terms of the equally weighted harmonic mean of precision and recall,"
            + math_display(r"F_1=2\frac{\mathrm{precision}\cdot\mathrm{recall}}{\mathrm{precision}+\mathrm{recall}}")
            + "As a side note, consider the unusual scenario where, after applying meta-labeling, there are many more positive cases than negative cases. A classifier that predicts all cases to be positive will achieve <code>TN=0</code> and <code>FN=0</code>, hence accuracy equals precision and recall is 1. Accuracy will be high, and F1 will not be smaller than accuracy, even though the classifier is not able to discriminate between the observed samples. One solution would be to switch the definitions of positive and negative cases, so that negative cases are predominant, and then score with F1.",
            "<strong>Negative log-loss:</strong> Negative log-loss was introduced in Chapter 9, Section 9.4, in the context of hyper-parameter tuning. Please refer to that section for details. The key conceptual difference between accuracy and negative log-loss is that negative log-loss takes into account not only whether our predictions were correct or not, but the probability of those predictions as well.",
        ]
        return "<ul>" + "".join(f"<li>{item}</li>" for item in items) + "</ul>"
    if block.kind == "ulist" and first.startswith(("Precision:", "Recall:", "Negative log-loss:")):
        return ""
    return None


def chapter_14_block_figure_html(block: Block) -> str | None:
    for number in ("14.1", "14.2", "14.3"):
        if block.caption.startswith(f"Figure {number}:"):
            return chapter_14_figure_html(number)
    return None


def chapter_04_paragraph_html(text: str) -> str | None:
    stripped = text.strip()
    suppress_exact = {
        "be (1) redundant to each other, and (2) very similar to out-of-bag observations.",
        "j=1",
        "Time",
    }
    if stripped in suppress_exact:
        return ""
    suppress_prefixes = (
        "] Xi , where yi was a function",
        "interval tj,0",
        "forced to reduce the outcome",
        "both labels spanning the same",
        "point t = 1",
        "1t,i = 1 if and only",
        "that the labels’ spans",
        "Chapter 3. Second",
        "T T label’s lifespan",
        "set in combination",
        "that 𝜑(1)",
        "that is the uniqueness",
        "̄u(2) =",
        "updated probabilities",
        "j ū k",
        "where 𝛿j(2)",
        "method. This can be verified",
        "overlaps are characterized",
        "⎡1 0 0",
        "⎥ 0⎥",
        "⎢0 1 0",
        "probabilities for the second",
        "tial bootstrap on the",
        "if numThreads==1",
        "with negligible absolute returns",
        "∑ hence",
        "tion. The final weight",
        "and d [x]",
        "Snippet 4.11 implements",
        "to cumulative uniqueness",
    )
    if stripped.startswith(suppress_prefixes):
        return ""
    if stripped.startswith("In Chapter 3 we assigned a label yi"):
        return (
            "<p>In Chapter 3 we assigned a label "
            + math_inline("y_i")
            + " to an observed feature "
            + math_inline("X_i")
            + ", where "
            + math_inline("y_i")
            + " was a function of price bars that occurred over an interval "
            + math_inline(r"[t_{i,0},t_{i,1}]")
            + ". When "
            + math_inline(r"t_{i,1}>t_{j,0}")
            + " and "
            + math_inline("i<j")
            + ", then "
            + math_inline("y_i")
            + " and "
            + math_inline("y_j")
            + " will both depend on a common return "
            + math_inline(r"r_{t_{j,0},\min\{t_{i,1},t_{j,1}\}}")
            + ", that is, the return over the interval "
            + math_inline(r"[t_{j,0},\min\{t_{i,1},t_{j,1}\}]")
            + ". The implication is that the series of labels, "
            + math_inline(r"\{y_i\}_{i=1,\ldots,I}")
            + ", are not IID whenever there is an overlap between any two consecutive outcomes, "
            + math_inline(r"\exists i\mid t_{i,1}>t_{i+1,0}")
            + ".</p>"
            "<p>Suppose that we circumvent this problem by restricting the bet horizon to "
            + math_inline(r"t_{i,1}\le t_{i+1,0}")
            + ". In this case there is no overlap, because every feature outcome is determined before or at the onset of the next observed feature. That would lead to coarse models where the features' sampling frequency would be limited by the horizon used to determine the outcome. On one hand, if we wished to investigate outcomes that lasted a month, features would have to be sampled with a frequency up to monthly. On the other hand, if we increased the sampling frequency to let's say daily, we would be forced to reduce the outcome's horizon to one day.</p>"
            "<p>Furthermore, if we wished to apply a path-dependent labeling technique, like the triple-barrier method, the sampling frequency would be subordinated to the first barrier's touch. No matter what you do, restricting the outcome's horizon to eliminate overlaps is a terrible solution. We must allow "
            + math_inline(r"t_{i,1}>t_{i+1,0}")
            + ", which brings us back to the problem of overlapping outcomes described earlier.</p>"
        )
    if stripped.startswith("This situation is characteristic of financial applications"):
        return chapter_04_p(stripped)
    if stripped.startswith("Two labels yi and yj are concurrent"):
        return (
            "<p>Two labels "
            + math_inline("y_i")
            + " and "
            + math_inline("y_j")
            + " are concurrent at "
            + math_inline("t")
            + " when both are a function of at least one common return, "
            + math_inline(r"r_{t-1,t}=\frac{p_t}{p_{t-1}}-1")
            + ". The overlap does not need to be perfect, in the sense of both labels spanning the same time interval. In this section we are going to compute the number of labels that are a function of a given return, "
            + math_inline(r"r_{t-1,t}")
            + ".</p>"
            "<p>First, for each time point "
            + math_inline(r"t=1,\ldots,T")
            + ", we form a binary array, "
            + math_inline(r"\{1_{t,i}\}_{i=1,\ldots,I}")
            + ", where "
            + math_inline(r"1_{t,i}\in\{0,1\}")
            + ". Variable "
            + math_inline("1_{t,i}=1")
            + " if and only if "
            + math_inline(r"[t_{i,0},t_{i,1}]")
            + " overlaps with "
            + math_inline(r"[t-1,t]")
            + " and "
            + math_inline("1_{t,i}=0")
            + " otherwise. Recall that the labels' spans "
            + math_inline(r"\{[t_{i,0},t_{i,1}]\}_{i=1,\ldots,I}")
            + " are defined by the "
            + chapter_04_code("t1")
            + " object introduced in Chapter 3. Second, we compute the number of labels concurrent at "
            + math_inline("t")
            + ", "
            + math_inline(r"c_t=\sum_{i=1}^{I}1_{t,i}")
            + ". Snippet 4.1 illustrates an implementation of this logic.</p>"
        )
    if stripped.startswith("for tIn,tOut in t1.iteritems"):
        return ""
    if stripped.startswith("In this section we are going to estimate a label’s uniqueness"):
        return (
            "<p>In this section we are going to estimate a label's uniqueness (non-overlap) as its average uniqueness over its lifespan. First, the uniqueness of a label "
            + math_inline("i")
            + " at time "
            + math_inline("t")
            + " is "
            + math_inline(r"u_{t,i}=1_{t,i}c_t^{-1}")
            + ". Second, the average uniqueness of label "
            + math_inline("i")
            + " is the average "
            + math_inline(r"u_{t,i}")
            + " over the label's lifespan,</p>"
            + math_display(r"\bar u_i=\left(\sum_{t=1}^{T}u_{t,i}\right)\left(\sum_{t=1}^{T}1_{t,i}\right)^{-1}")
            + "<p>This average uniqueness can also be interpreted as the reciprocal of the harmonic average of "
            + math_inline("c_t")
            + " over the event's lifespan. Figure 4.1 plots the histogram of uniqueness values derived from an object "
            + chapter_04_code("t1")
            + ". Snippet 4.2 implements this calculation.</p>"
        )
    if stripped.startswith("Note that we are making use again"):
        return (
            "<p>Note that we are making use again of the function "
            + chapter_04_code("mpPandasObj")
            + ", which speeds up calculations via multiprocessing (see Chapter 20). Computing the average uniqueness associated with label "
            + math_inline("i")
            + ", "
            + math_inline(r"\bar u_i")
            + ", requires information that is not available until a future time, "
            + chapter_04_code("events['t1']")
            + ". This is not a problem, because "
            + math_inline(r"\{\bar u_i\}_{i=1,\ldots,I}")
            + " are used on the training set in combination with label information, and not on the testing set. These "
            + math_inline(r"\{\bar u_i\}_{i=1,\ldots,I}")
            + " are not used for forecasting the label, hence there is no information leakage. This procedure allows us to assign a uniqueness score between 0 and 1 for each observed feature, in terms of non-overlapping outcomes.</p>"
        )
    if stripped.startswith("The probability of not selecting a particular item"):
        return (
            "<p>The probability of not selecting a particular item "
            + math_inline("i")
            + " after "
            + math_inline("I")
            + " draws with replacement on a set of "
            + math_inline("I")
            + " items is "
            + math_inline(r"(1-I^{-1})^I")
            + ". As the sample size grows, that probability converges to the asymptotic value "
            + math_inline(r"\lim_{I\to\infty}(1-I^{-1})^I=e^{-1}")
            + ". That means that the number of unique observations drawn is expected to be "
            + math_inline(r"(1-e^{-1})\approx 2/3")
            + ".</p>"
            "<p>Suppose that the maximum number of non-overlapping outcomes is "
            + math_inline(r"K\le I")
            + ". Following the same argument, the probability of not selecting a particular item "
            + math_inline("i")
            + " after "
            + math_inline("I")
            + " draws with replacement on a set of "
            + math_inline("I")
            + " items is "
            + math_inline(r"(1-K^{-1})^I")
            + ". As the sample size grows, that probability can be approximated as "
            + math_inline(r"(1-I^{-1})^{IK/I}\approx e^{-K/I}")
            + ". That means that the number of unique observations drawn is expected to be "
            + math_inline(r"1-e^{-K/I}\le 1-e^{-1}")
            + ". The implication is that incorrectly assuming IID draws leads to oversampling.</p>"
            "<p>When sampling with replacement (bootstrap) on observations with "
            + math_inline(r"I^{-1}\sum_{i=1}^{I}\bar u_i\ll 1")
            + ", it becomes increasingly likely that in-bag observations will be (1) redundant to each other, and (2) very similar to out-of-bag observations.</p>"
        )
    if stripped.startswith("Redundancy of draws makes the bootstrap inefficient"):
        return (
            "<p>Redundancy of draws makes the bootstrap inefficient (see Chapter 6). For example, in the case of a random forest, all trees in the forest will essentially be very similar copies of a single overfit decision tree. And because the random sampling makes out-of-bag examples very similar to the in-bag ones, out-of-bag accuracy will be grossly inflated. We will address this second issue in Chapter 7, when we study cross-validation under non-IID observations. For the moment, let us concentrate on the first issue, namely bagging under observations where "
            + math_inline(r"I^{-1}\sum_{i=1}^{I}\bar u_i\ll 1")
            + ".</p><p>A first solution is to drop overlapping outcomes before performing the bootstrap. Because overlaps are not perfect, dropping an observation just because there is a partial overlap will result in an extreme loss of information. I do not advise you to follow this solution.</p>"
        )
    if stripped.startswith("A second and better solution"):
        return (
            "<p>A second and better solution is to utilize the average uniqueness, "
            + math_inline(r"I^{-1}\sum_{i=1}^{I}\bar u_i")
            + ", to reduce the undue influence of outcomes that contain redundant information. Accordingly, we could sample only a fraction "
            + chapter_04_code("out['tW'].mean()")
            + " of the observations, or a small multiple of that. In sklearn, the "
            + chapter_04_code("sklearn.ensemble.BaggingClassifier")
            + " class accepts an argument "
            + chapter_04_code("max_samples")
            + ", which can be set to "
            + chapter_04_code("max_samples=out['tW'].mean()")
            + ". In this way, we enforce that the in-bag observations are not sampled at a frequency much higher than their uniqueness. Random forests do not offer that "
            + chapter_04_code("max_samples")
            + " functionality, however, a solution is to bag a large number of decision trees. We will discuss this solution further in Chapter 6.</p>"
        )
    if stripped.startswith("A third and better solution"):
        return (
            "<p>A third and better solution is to perform a sequential bootstrap, where draws are made according to a changing probability that controls for redundancy. Rao et al. [1997] propose sequential resampling with replacement until "
            + math_inline("K")
            + " distinct original observations appear. Although interesting, their scheme does not fully apply to our financial problem. In the following sections we introduce an alternative method that addresses directly the problem of overlapping outcomes.</p>"
            "<p>First, an observation "
            + math_inline("X_i")
            + " is drawn from a uniform distribution, "
            + math_inline(r"i\sim U[1,I]")
            + ", that is, the probability of drawing any particular value "
            + math_inline("i")
            + " is originally "
            + math_inline(r"\delta_i^{(1)}=I^{-1}")
            + ". For the second draw, we wish to reduce the probability of drawing an observation "
            + math_inline("X_j")
            + " with a highly overlapping outcome. Remember, a bootstrap allows sampling with repetition, so it is still possible to draw "
            + math_inline("X_i")
            + " again, but we wish to reduce its likelihood, since there is an overlap between "
            + math_inline("X_i")
            + " and itself. Let us denote as "
            + math_inline(r"\varphi")
            + " the sequence of draws so far, which may include repetitions. Until now, we know "
            + math_inline(r"\varphi^{(1)}=\{i\}")
            + ".</p>"
            "<p>The uniqueness of "
            + math_inline("j")
            + " at time "
            + math_inline("t")
            + " is</p>"
            + math_display(r"u_{t,j}^{(2)}=1_{t,j}\left(1+\sum_{k\in\varphi^{(1)}}1_{t,k}\right)^{-1}")
            + "<p>as that is the uniqueness that results from adding alternative "
            + math_inline("j")
            + "'s to the existing sequence of draws "
            + math_inline(r"\varphi^{(1)}")
            + ". The average uniqueness of "
            + math_inline("j")
            + " is the average "
            + math_inline(r"u_{t,j}^{(2)}")
            + " over "
            + math_inline("j")
            + "'s lifespan, "
            + math_inline(r"\bar u_j^{(2)}=\left(\sum_{t=1}^{T}u_{t,j}^{(2)}\right)\left(\sum_{t=1}^{T}1_{t,j}\right)^{-1}")
            + ". We can now make a second draw based on the updated probabilities "
            + math_inline(r"\{\delta_j^{(2)}\}_{j=1,\ldots,I}")
            + ":</p>"
            + math_display(r"\delta_j^{(2)}=\bar u_j^{(2)}\left(\sum_{k=1}^{I}\bar u_k^{(2)}\right)^{-1}")
            + "<p>where "
            + math_inline(r"\{\delta_j^{(2)}\}_{j=1,\ldots,I}")
            + " are scaled to add up to 1, "
            + math_inline(r"\sum_{j=1}^{I}\delta_j^{(2)}=1")
            + ". We can now do a second draw, update "
            + math_inline(r"\varphi^{(2)}")
            + " and re-evaluate "
            + math_inline(r"\{\delta_j^{(3)}\}_{j=1,\ldots,I}")
            + ". The process is repeated until "
            + math_inline("I")
            + " draws have taken place. This sequential bootstrap scheme has the advantage that overlaps (even repetitions) are still possible, but decreasingly likely. The sequential bootstrap sample will be much closer to IID than samples drawn from the standard bootstrap method. This can be verified by measuring an increase in "
            + math_inline(r"I^{-1}\sum_{i=1}^{I}\bar u_i")
            + ", relative to the standard bootstrap method.</p>"
        )
    if stripped.startswith("Snippet 4.3 derives an indicator matrix"):
        return (
            "<p>Snippet 4.3 derives an indicator matrix from two arguments: the index of bars ("
            + chapter_04_code("barIx")
            + "), and the pandas Series "
            + chapter_04_code("t1")
            + ", which we used multiple times in Chapter 3. As a reminder, "
            + chapter_04_code("t1")
            + " is defined by an index containing the time at which the features are observed, and a values array containing the time at which the label is determined. The output of this function is a binary matrix indicating what (price) bars influence the label for each observation.</p>"
        )
    if stripped.startswith("Snippet 4.5 gives us the index"):
        return (
            "<p>Snippet 4.5 gives us the index of the features sampled by sequential bootstrap. The inputs are the indicator matrix ("
            + chapter_04_code("indM")
            + ") and an optional sample length ("
            + chapter_04_code("sLength")
            + "), with a default value of as many draws as columns in "
            + chapter_04_code("indM")
            + ".</p>"
        )
    if stripped.startswith("Consider a set of labels yi"):
        return (
            "<p>Consider a set of labels "
            + math_inline(r"\{y_i\}_{i=1,2,3}")
            + ", where label "
            + math_inline("y_1")
            + " is a function of return "
            + math_inline("r_{0,3}")
            + ", label "
            + math_inline("y_2")
            + " is a function of return "
            + math_inline("r_{2,4}")
            + ", and label "
            + math_inline("y_3")
            + " is a function of return "
            + math_inline("r_{4,6}")
            + ". The outcomes' overlaps are characterized by this indicator matrix "
            + math_inline(r"\{1_{t,i}\}")
            + ":</p>"
            + math_display(r"\{1_{t,i}\}=\begin{bmatrix}1&0&0\\1&0&0\\1&1&0\\0&1&0\\0&0&1\\0&0&1\end{bmatrix}")
        )
    if stripped.startswith("The procedure starts with 𝜑(0)"):
        return (
            "<p>The procedure starts with "
            + math_inline(r"\varphi^{(0)}=\emptyset")
            + ", and a uniform distribution of probability, "
            + math_inline(r"\delta_i=1/3,\ \forall i=1,2,3")
            + ". Suppose that we randomly draw a number from "
            + math_inline(r"\{1,2,3\}")
            + ", and 2 is selected. Before we make a second draw on "
            + math_inline(r"\{1,2,3\}")
            + " (remember, a bootstrap samples with repetition), we need to adjust the probabilities. The set of observations drawn so far is "
            + math_inline(r"\varphi^{(1)}=\{2\}")
            + ".</p><p>The average uniqueness for the first feature is "
            + math_inline(r"\bar u_1^{(2)}=(1+1+\tfrac{1}{2})/3=5/6<1")
            + ", and for the second feature is "
            + math_inline(r"\bar u_2^{(2)}=(\tfrac{1}{2}+\tfrac{1}{2})/2=1/2<1")
            + ". The probabilities for the second draw are "
            + math_inline(r"\delta^{(2)}=\{5/14,3/14,6/14\}")
            + ".</p><p>Two points are worth mentioning: (1) The lowest probability goes to the feature that was picked in the first draw, as that would exhibit the highest overlap; and (2) among the two possible draws outside "
            + math_inline(r"\varphi^{(1)}")
            + ", the greater probability goes to "
            + math_inline(r"\delta_3^{(2)}")
            + ", as that is the label with no overlap to "
            + math_inline(r"\varphi^{(1)}")
            + ". Suppose that the second draw selects number 3. We leave as an exercise the update of the probabilities "
            + math_inline(r"\{\delta^{(3)}\}")
            + " for the third and final draw. Snippet 4.6 runs a sequential bootstrap on the "
            + math_inline(r"\{1_{t,i}\}")
            + " indicator matrix in this example.</p>"
        )
    if stripped.startswith("We can evaluate the efficiency"):
        return chapter_04_p(stripped)
    if stripped.startswith("Snippet 4.8 takes that random t1 series"):
        return chapter_04_p(stripped)
    if stripped.startswith("These operations have to be repeated"):
        return chapter_04_p(stripped)
    if stripped.startswith("In the previous section we learned a method"):
        return (
            "<p>In the previous section we learned a method to bootstrap samples closer to IID. In this section we will introduce a method to weight those samples for the purpose of training an ML algorithm. Highly overlapping outcomes would have disproportionate weights if considered equal to non-overlapping outcomes. At the same time, labels associated with large absolute returns should be given more importance than labels with negligible absolute returns. In short, we need to weight observations by some function of both uniqueness and absolute return.</p>"
            "<p>When labels are a function of the return sign ("
            + math_inline(r"\{-1,1\}")
            + " for standard labeling or "
            + math_inline(r"\{0,1\}")
            + " for meta-labeling), the sample weights can be defined in terms of the sum of the attributed returns over the event's lifespan, "
            + math_inline(r"[t_{i,0},t_{i,1}]")
            + ":</p>"
            + math_display(r"\tilde w_i=\left|\sum_{t=t_{i,0}}^{t_{i,1}}\frac{r_{t-1,t}}{c_t}\right|")
            + math_display(r"w_i=\tilde w_i I\left(\sum_{j=1}^{I}\tilde w_j\right)^{-1}")
            + "<p>hence "
            + math_inline(r"\sum_{i=1}^{I}w_i=I")
            + ". We have scaled these weights to add up to "
            + math_inline("I")
            + ", since libraries (including sklearn) usually define algorithmic parameters assuming a default weight of 1. The rationale for this method is that we wish to weight an observation as a function of the absolute log returns that can be attributed uniquely to it. However, this method will not work if there is a “neutral” (return below threshold) case. For that case, lower returns should be assigned higher weights, not the reciprocal. The “neutral” case is unnecessary, as it can be implied by a “-1” or “1” prediction with low confidence. This is one of several reasons I would generally advise you to drop “neutral” cases. Snippet 4.10 implements this method.</p>"
        )
    if stripped.startswith("Markets are adaptive systems"):
        return (
            "<p>Markets are adaptive systems (Lo [2017]). As markets evolve, older examples are less relevant than the newer ones. Consequently, we would typically like sample weights to decay as new observations arrive. Let "
            + math_inline(r"d[x]\ge0,\ \forall x\in\left[0,\sum_{i=1}^{I}\bar u_i\right]")
            + " be the time-decay factors that will multiply the sample weights derived in the previous section. The final weight has no decay, "
            + math_inline(r"d\left[\sum_{i=1}^{I}\bar u_i\right]=1")
            + ", and all other weights will be adjusted relative to that.</p>"
            "<p>Let "
            + math_inline(r"c\in(-1,1]")
            + " be a user-defined parameter that determines the decay function as follows: for "
            + math_inline(r"c\in[0,1]")
            + ", "
            + math_inline("d[1]=c")
            + ", with linear decay; for "
            + math_inline(r"c\in(-1,0)")
            + ", "
            + math_inline(r"d\left[-c\sum_{i=1}^{I}\bar u_i\right]=0")
            + ", with linear decay between "
            + math_inline(r"-c\sum_{i=1}^{I}\bar u_i")
            + " and "
            + math_inline(r"\sum_{i=1}^{I}\bar u_i")
            + ", and "
            + math_inline(r"d[x]=0\ \forall x\le -c\sum_{i=1}^{I}\bar u_i")
            + ". For a linear piecewise function "
            + math_inline(r"d=\max\{0,a+bx\}")
            + ", such requirements are met by the following boundary conditions:</p>"
        )
    if stripped.startswith("Figure 4.3 shows the decayed weights"):
        return (
            "<p>Figure 4.3 shows the decayed weights, "
            + chapter_04_code("out['w']*df")
            + ", after applying the decay factors for "
            + math_inline(r"c\in\{1,.75,.5,0,-.25,-.5\}")
            + ". Although not necessarily practical, the procedure allows the possibility of generating weights that increase as they get older, by setting "
            + math_inline("c>1")
            + ".</p>"
        )
    if stripped.startswith("In financial applications, the standard labels"):
        return (
            "<p>In financial applications, the standard labels of a classification algorithm are "
            + math_inline(r"\{-1,1\}")
            + ", where the zero (or neutral) case will be implied by a prediction with probability only slightly above 0.5 and below some neutral threshold. There is no reason for favoring accuracy of one class over the other, and as such a good default is to assign "
            + chapter_04_code("class_weight='balanced'")
            + ". This choice re-weights observations so as to simulate that all classes appeared with equal frequency. In the context of bagging classifiers, you may want to consider the argument "
            + chapter_04_code("class_weight='balanced_subsample'")
            + ", which means that "
            + chapter_04_code("class_weight='balanced'")
            + " will be applied to the in-bag bootstrapped samples, rather than to the entire dataset. For full details, it is helpful to read the source code implementing "
            + chapter_04_code("class_weight")
            + " in sklearn. Please also be aware of this reported bug: https://github.com/scikit-learn/scikit-learn/issues/4324.</p>"
        )
    cleaned = chapter_04_text_html(stripped)
    if cleaned != mathify_general_text(stripped):
        return f"<p>{cleaned}</p>"
    return None


def chapter_16_paragraph_html(text: str) -> str | None:
    stripped = text.strip()
    heading = chapter_16_appendix_heading(stripped)
    if heading is not None:
        return heading
    if stripped in {
        "T",
        "t t t t t t t=1 t=1 t=1 t=1",
        "⎜ ⏟⏟⎟",
        "⎜ ⏟⏟⏟⎟",
        "5 Identity Correlated III-Conditioned 4 Singular",
        "Eigenvalues",
        "Variable #",
        "(a)",
        "(b)",
        "(c)",
        "⎢ ⎥ ⎢ ⎥",
        "⎢ ⎥",
        "̇",
        "⎣ ⎦ ⎣ ⎦",
    }:
        return ""
    if stripped.startswith(("⎢", "⎣")):
        return ""
    suppress_prefixes = (
        "[0, 1], di,j =",
        "in {1, … , i, … , N}. This allows us",
        "the difference between distance metrics",
        "Example 16.1 Encoding",
        "Example 16.2 Euclidean",
        "Example 16.3 Clustering",
        "Example 16.4 Updating",
        "Example 16.5 Updating",
        "Example 16.6 Recursion",
        "⎢ .9747 1.1225",
        "ym,2 , that is ym,3",
        "(d) re-scale allocations wn",
        "wi ≤ 1, ∀i = 1",
        "Let us prove that d[x, y]",
        "distance between the two vectors is",
        "Third, we derive the Euclidean distance d[x, y] as",
        "In other words, the distance d[x, y] is a linear multiple",
        "Similarly, we can prove that d[x, y]",
        "sgn [",
        "minimum variance portfolio. If V is diagonal",
        "two bisections of a subset.",
    )
    if stripped.startswith(suppress_prefixes):
        return ""
    if stripped.startswith("1 A short version of this chapter appeared"):
        return '<p class="footnote">1 A short version of this chapter appeared in the Journal of Portfolio Management, Vol. 42, No. 4, pp. 59-69, Summer of 2016.</p>'
    if stripped.startswith("pp. 59–69"):
        return ""
    if stripped.startswith("The condition number of a covariance"):
        return (
            "<p>The condition number of a covariance, correlation (or normal, thus diagonalizable) matrix is the absolute value of the ratio between its maximal and minimal (by moduli) eigenvalues. Figure 16.1 plots the sorted eigenvalues of several correlation matrices, where the condition number is the ratio between the first and last values of each line. This number is lowest for a diagonal correlation matrix, which is its own inverse. As we add correlated (multicollinear) investments, the condition number grows. At some point, the condition number is so high that numerical errors make the inverse matrix too unstable: A small change on any entry will lead to a very different inverse. This is Markowitz's curse: The more correlated the investments, the greater the need for diversification, and yet the more likely we will receive unstable solutions. The benefits of diversification often are more than offset by estimation errors.</p>"
            "<p>Increasing the size of the covariance matrix will only make matters worse, as each covariance coefficient is estimated with fewer degrees of freedom. In general, we need at least "
            + math_inline(r"\frac{1}{2}N(N+1)")
            + " independent and identically distributed (IID) observations in order</p>"
        )
    if stripped.startswith("Consider a TxN matrix of observations X"):
        return (
            "<p>Consider a "
            + math_inline(r"T\times N")
            + " matrix of observations "
            + math_inline("X")
            + ", such as returns series of "
            + math_inline("N")
            + " variables over "
            + math_inline("T")
            + " periods. We would like to combine these "
            + math_inline("N")
            + " column-vectors into a hierarchical structure of clusters, so that allocations can flow downstream through a tree graph.</p>"
            "<p>First, we compute an "
            + math_inline(r"N\times N")
            + " correlation matrix with entries "
            + math_inline(r"\rho=\{\rho_{i,j}\}_{i,j=1,\ldots,N}")
            + ", where "
            + math_inline(r"\rho_{i,j}=\rho[X_i,X_j]")
            + ". We define the distance measure "
            + math_inline(r"d:(X_i,X_j)\subset B\to\mathbb{R}")
            + " by "
            + math_inline(r"d_{i,j}=d[X_i,X_j]=\sqrt{\frac{1}{2}(1-\rho_{i,j})}\in[0,1]")
            + ", where "
            + math_inline("B")
            + " is the Cartesian product of items in "
            + math_inline(r"\{1,\ldots,i,\ldots,N\}")
            + ". This allows us to compute an "
            + math_inline(r"N\times N")
            + " distance matrix "
            + math_inline(r"D=\{d_{i,j}\}_{i,j=1,\ldots,N}")
            + ". Matrix "
            + math_inline("D")
            + " is a proper metric space (see Appendix 16.A.1 for a proof), in the sense that "
            + math_inline(r"d[x,y]\ge0")
            + " (non-negativity), "
            + math_inline(r"d[x,y]=0\Leftrightarrow X=Y")
            + " (coincidence), "
            + math_inline(r"d[x,y]=d[Y,X]")
            + " (symmetry), and "
            + math_inline(r"d[X,Z]\le d[x,y]+d[Y,Z]")
            + " (sub-additivity). See Example 16.1.</p>"
        )
    if stripped.startswith("⎡ 1 .7"):
        return chapter_16_example_html(
            r"Example 16.1 Encoding a correlation matrix \(\rho\) as a distance matrix \(D\)",
            r"\{\rho_{i,j}\}=\begin{bmatrix}1&.7&.2\\.7&1&-.2\\.2&-.2&1\end{bmatrix}\to\{d_{i,j}\}=\begin{bmatrix}0&.3873&.6325\\.3873&0&.7746\\.6325&.7746&0\end{bmatrix}",
        )
    if stripped.startswith("Second, we compute the Euclidean distance"):
        return (
            "<p>Second, we compute the Euclidean distance between any two column-vectors of "
            + math_inline("D")
            + ", "
            + math_inline(r"\tilde d:(D_i,D_j)\subset B\to\mathbb{R}")
            + " with "
            + math_inline(r"\tilde d_{i,j}\in[0,\sqrt{N}]")
            + ":</p>"
            + math_display(r"\tilde d_{i,j}=\tilde d[D_i,D_j]=\sqrt{\sum_{n=1}^{N}(d_{n,i}-d_{n,j})^2}")
            + "<p>Note the difference between distance metrics "
            + math_inline(r"d_{i,j}")
            + " and "
            + math_inline(r"\tilde d_{i,j}")
            + ". Whereas "
            + math_inline(r"d_{i,j}")
            + " is defined on column-vectors of "
            + math_inline("X")
            + ", "
            + math_inline(r"\tilde d_{i,j}")
            + " is defined on column-vectors of "
            + math_inline("D")
            + " (a distance of distances). Therefore, "
            + math_inline(r"\tilde d")
            + " is a distance defined over the entire metric space "
            + math_inline("D")
            + ", as each "
            + math_inline(r"\tilde d_{i,j}")
            + " is a function of the entire correlation matrix (rather than a particular cross-correlation pair). See Example 16.2.</p>"
        )
    if stripped.startswith("⎡ 0 .3873"):
        return chapter_16_example_html(
            r"Example 16.2 Euclidean distance of correlation distances",
            r"\{d_{i,j}\}=\begin{bmatrix}0&.3873&.6325\\.3873&0&.7746\\.6325&.7746&0\end{bmatrix}\to\{\tilde d_{i,j}\}_{i,j=\{1,2,3\}}=\begin{bmatrix}0&.5659&.9747\\.5659&0&1.1225\\.9747&1.1225&0\end{bmatrix}",
        )
    if stripped.startswith("⎣.6325 .7746 0"):
        return ""
    if stripped.startswith("Third, we cluster together"):
        return (
            "<p>Third, we cluster together the pair of columns "
            + math_inline(r"(i^*,j^*)")
            + " such that "
            + math_inline(r"(i^*,j^*)=\arg\min_{(i,j),\,i\ne j}\{\tilde d_{i,j}\}")
            + ", and denote this cluster as "
            + math_inline("u[1]")
            + ". See Example 16.3.</p>"
        )
    if stripped.startswith("⎡ 0 .5659 .9747 ⎤"):
        return chapter_16_example_html(
            "Example 16.3 Clustering items",
            r"\{\tilde d_{i,j}\}_{i,j=\{1,2,3\}}=\begin{bmatrix}0&.5659&.9747\\.5659&0&1.1225\\.9747&1.1225&0\end{bmatrix}\to u[1]=(1,2)",
        )
    if stripped.startswith("Fourth, we need to define"):
        return (
            "<p>Fourth, we need to define the distance between a newly formed cluster "
            + math_inline("u[1]")
            + " and the single (unclustered) items, so that "
            + math_inline(r"\{\tilde d_{i,j}\}")
            + " may be updated. In hierarchical clustering analysis, this is known as the linkage criterion. For example, we can define the distance between an item "
            + math_inline("i")
            + " of "
            + math_inline(r"\tilde d")
            + " and the new cluster "
            + math_inline("u[1]")
            + " as "
            + math_inline(r"\dot d_{i,u[1]}=\min[\{\tilde d_{i,j}\}_{j\in u[1]}]")
            + " (the nearest point algorithm). See Example 16.4.</p>"
        )
    if stripped.startswith("distance between an item i of"):
        return ""
    if stripped.startswith("min [0, .5659]"):
        return chapter_16_example_html(
            r"Example 16.4 Updating matrix \(\{\tilde d_{i,j}\}\) with the new cluster \(u\)",
            r"u[1]=(1,2)\to\{\dot d_{i,u[1]}\}=\begin{bmatrix}\min[0,.5659]\\\min[.5659,0]\\\min[.9747,1.1225]\end{bmatrix}=\begin{bmatrix}0\\0\\.9747\end{bmatrix}",
        )
    if stripped.startswith("Fifth, matrix"):
        return (
            "<p>Fifth, matrix "
            + math_inline(r"\{\tilde d_{i,j}\}")
            + " is updated by appending "
            + math_inline(r"\dot d_{i,u[1]}")
            + " and dropping the clustered columns and rows "
            + math_inline(r"j\in u[1]")
            + ". See Example 16.5.</p>"
        )
    if stripped.startswith("⎡ 0 .5659 .9747 0"):
        return chapter_16_example_html(
            r"Example 16.5 Updating matrix \(\{\tilde d_{i,j}\}\) with the new cluster \(u\)",
            r"\{\tilde d_{i,j}\}_{i,j=\{1,2,3,4\}}=\begin{bmatrix}0&.5659&.9747&0\\.5659&0&1.1225&0\\.9747&1.1225&0&.9747\\0&0&.9747&0\end{bmatrix},\qquad \{\tilde d_{i,j}\}_{i,j=\{3,4\}}=\begin{bmatrix}0&.9747\\.9747&0\end{bmatrix}",
        )
    if stripped.startswith("Example 16.5"):
        return ""
    if stripped.startswith("Sixth, applied recursively"):
        return (
            "<p>Sixth, applied recursively, steps 3, 4, and 5 allow us to append "
            + math_inline("N-1")
            + " such clusters to matrix "
            + math_inline("D")
            + ", at which point the final cluster contains all of the original items, and the clustering algorithm stops. See Example 16.6.</p>"
        )
    if stripped.startswith("Figure 16.3 displays"):
        return (
            "<p>Figure 16.3 displays the clusters formed at each iteration for this example, as well as the distances "
            + math_inline(r"\tilde d_{i^*,j^*}")
            + " that triggered every cluster (third step). This procedure can be applied to a wide array of distance metrics "
            + math_inline(r"d_{i,j}")
            + ", "
            + math_inline(r"\tilde d_{i,j}")
            + " and "
            + math_inline(r"\dot d_{i,u}")
            + ", beyond those illustrated in this chapter. See Rokach and Maimon [2005] for alternative metrics, the discussion on Fiedler's vector and Stewart's spectral clustering method in Brualdi [2010], as well as algorithms in the scipy library.<sup>2</sup> Snippet 16.1 provides an example of tree clustering using scipy functionality.</p>"
        )
    if stripped.startswith("well as algorithms in the scipy library"):
        return ""
    if stripped.startswith("http://docs.scipy.org/doc/scipy/reference/generated/scipy.spatial.distance.pdist.html"):
        return (
            '<p class="footnote"><sup>2</sup> '
            '<a href="http://docs.scipy.org/doc/scipy/reference/generated/scipy.spatial.distance.pdist.html">http://docs.scipy.org/doc/scipy/reference/generated/scipy.spatial.distance.pdist.html</a> '
            '<a href="http://docs.scipy.org/doc/scipy-0.16.0/reference/generated/scipy.cluster.hierarchy.linkage.html">http://docs.scipy.org/doc/scipy-0.16.0/reference/generated/scipy.cluster.hierarchy.linkage.html</a>.</p>'
        )
    if stripped.startswith("This stage allows us to define a linkage matrix"):
        return (
            "<p>This stage allows us to define a linkage matrix as an "
            + math_inline(r"(N-1)\times4")
            + " matrix with structure "
            + math_inline(r"Y=\{(y_{m,1},y_{m,2},y_{m,3},y_{m,4})\}_{m=1,\ldots,N-1}")
            + " (i.e., with one 4-tuple per cluster). Items "
            + math_inline(r"(y_{m,1},y_{m,2})")
            + " report the constituents. Item "
            + math_inline(r"y_{m,3}")
            + " reports the distance between "
            + math_inline(r"y_{m,1}")
            + " and "
            + math_inline(r"y_{m,2}")
            + ", that is "
            + math_inline(r"y_{m,3}=\tilde d_{y_{m,1},y_{m,2}}")
            + ". Item "
            + math_inline(r"y_{m,4}\le N")
            + " reports the number of original items included in cluster "
            + math_inline("m")
            + ".</p>"
        )
    if stripped.startswith("This stage reorganizes the rows and columns"):
        return (
            "<p>This stage reorganizes the rows and columns of the covariance matrix, so that the largest values lie along the diagonal. This quasi-diagonalization of the covariance matrix (without requiring a change of basis) renders a useful property: Similar investments are placed together, and dissimilar investments are placed far apart (see Figures 16.5 and 16.6 for an example). The algorithm works as follows: We know that each row of the linkage matrix merges two branches into one. We replace clusters in "
            + math_inline(r"(y_{N-1,1},y_{N-1,2})")
            + " with their constituents recursively, until no clusters remain. These replacements preserve the order of the clustering. The output is a sorted list of original (unclustered) items. This logic is implemented in Snippet 16.2.</p>"
        )
    if stripped.startswith("Step 3b takes advantage"):
        return (
            "<p>Step 3b takes advantage of the quasi-diagonalization bottom-up, because it defines the variance of the partition "
            + math_inline(r"L_i^{(j)}")
            + " using inverse-variance weightings "
            + math_inline(r"\tilde w_i^{(j)}")
            + ". Step 3c takes advantage of the quasi-diagonalization top-down, because it splits the weight in inverse proportion to the cluster's variance. This algorithm guarantees that "
            + math_inline(r"0\le w_i\le1,\ \forall i=1,\ldots,N")
            + ", and "
            + math_inline(r"\sum_{i=1}^{N}w_i=1")
            + ", because at each iteration we are splitting the weights received from higher hierarchical levels. Constraints can be easily introduced in this stage, by replacing the equations in steps 3c, 3d, and 3e according to the user's preferences. Stage 3 is implemented in Snippet 16.3.</p>"
        )
    if stripped.startswith("This concludes a first description"):
        return (
            "<p>This concludes a first description of the HRP algorithm, which solves the allocation problem in best-case deterministic logarithmic time, "
            + math_inline(r"T(n)=\mathcal{O}(\log_2[n])")
            + ", and worst-case deterministic linear time, "
            + math_inline(r"T(n)=\mathcal{O}(n)")
            + ". Next, we will put to practice what we have learned, and evaluate the method's accuracy out-of-sample.</p>"
        )
    if stripped.startswith("We begin by simulating a matrix of observations X"):
        return (
            "<p>We begin by simulating a matrix of observations "
            + math_inline("X")
            + ", of order "
            + math_inline(r"10000\times10")
            + ". The correlation matrix is visualized in Figure 16.4 as a heatmap. Figure 16.5 displays the dendogram of the resulting clusters (stage 1). Figure 16.6 shows the same correlation matrix, reorganized in blocks according to the identified clusters (stage 2). Appendix 16.A.3 provides the code used to generate this numerical example. On this random data, we compute HRP's allocations (stage 3), and compare them to the allocations from two competing methodologies: (1) Quadratic optimization, as represented by CLA's minimum-variance portfolio (the only portfolio of the efficient frontier that does not depend on returns' means); and (2) traditional risk parity, exemplified by the Inverse-Variance Portfolio (IVP). See Bailey and López de Prado [2013] for a comprehensive implementation of CLA, and Appendix 16.A.2 for a derivation of IVP.</p>"
        )
    if stripped.startswith("derivation of IVP. We apply the standard constraints"):
        return (
            "<p>We apply the standard constraints "
            + math_inline(r"0\le w_i\le1")
            + " (non-negativity), "
            + math_inline(r"\forall i=1,\ldots,N")
            + ", and "
            + math_inline(r"\sum_{i=1}^{N}w_i=1")
            + " (full investment). Incidentally, the condition number for the covariance matrix in this example is only 150.9324, not particularly high and therefore not unfavorable to CLA.</p>"
            "<p>From the allocations in Table 16.1, we can appreciate a few stylized features: First, CLA concentrates 92.66% of the allocation on the top-5 holdings, while HRP concentrates only 62.57%. Second, CLA assigns zero weight to 3 investments (without the "
            + math_inline(r"0\le w_i")
            + " constraint, the allocation would have been negative). Third, HRP seems to find a compromise between CLA's concentrated solution and traditional risk parity's IVP allocation. The reader can use the code in Appendix 16.A.3 to verify that these findings generally hold for alternative random covariance matrices.</p>"
            "<p>What drives CLA's extreme concentration is its goal of minimizing the portfolio's risk. And yet both portfolios have a very similar standard deviation ("
            + math_inline(r"\sigma_{\mathrm{HRP}}=0.4640")
            + ", "
            + math_inline(r"\sigma_{\mathrm{CLA}}=0.4486")
            + "). So CLA has discarded half of the investment universe in favor of a minor risk reduction. The reality of course is that CLA's portfolio is deceitfully diversified, because any distress situation affecting the top-5 allocations will have a much greater negative impact on CLA's than on HRP's portfolio.</p>"
        )
    if stripped.startswith("∀i = 1"):
        return ""
    if stripped.startswith("In our numerical example, CLA"):
        return (
            "<p>In our numerical example, CLA's portfolio has lower risk than HRP's in-sample. However, the portfolio with minimum variance in-sample is not necessarily the one with minimum variance out-of-sample. It would be all too easy for us to pick a particular historical dataset where HRP outperforms CLA and IVP (see Bailey and López de Prado [2014], and recall our discussion of selection bias in Chapter 11). Instead, in this section we follow the backtesting paradigm explained in Chapter 13, and evaluate via Monte Carlo the performance out-of-sample of HRP against CLA's minimum-variance and traditional risk parity's IVP allocations. This will also help us understand what features make a method preferable to the rest, regardless of anecdotal counter-examples.</p>"
            "<p>First, we generate 10 series of random Gaussian returns (520 observations, equivalent to 2 years of daily history), with 0 mean and an arbitrary standard deviation of 10%. Real prices exhibit frequent jumps (Merton [1976]) and returns are not cross-sectionally independent, so we must add random shocks and a random correlation structure to our generated data. Second, we compute HRP, CLA, and IVP portfolios by looking back at 260 observations (a year of daily history). These portfolios are re-estimated and rebalanced every 22 observations (equivalent to a monthly frequency). Third, we compute the out-of-sample returns associated with those three portfolios. This procedure is repeated 10,000 times.</p>"
            "<p>All mean portfolio returns out-of-sample are essentially 0, as expected. The critical difference comes from the variance of the out-of-sample portfolio returns: "
            + math_inline(r"\sigma_{\mathrm{CLA}}^2=0.1157")
            + ", "
            + math_inline(r"\sigma_{\mathrm{IVP}}^2=0.0928")
            + ", and "
            + math_inline(r"\sigma_{\mathrm{HRP}}^2=0.0671")
            + ". Although CLA's goal is to deliver the lowest variance (that is the objective of its optimization program), its performance happens to exhibit the highest variance out-of-sample, and 72.47% greater variance than HRP's. This experimental finding is consistent with the historical evidence in De Miguel et al. [2009]. In other words, HRP would improve the out-of-sample Sharpe ratio of a CLA strategy by about 31.3%, a rather significant boost. Assuming that the covariance matrix is diagonal brings some stability to the IVP; however, its variance is still 38.24% greater than HRP's. This variance reduction out-of-sample is critically important to risk parity investors, given their use of substantial leverage. See Bailey et al. [2014] for a broader discussion of in-sample vs. out-of-sample performance.</p>"
            "<p>The mathematical proof for HRP's outperformance over Markowitz's CLA and traditional risk parity's IVP is somewhat involved and beyond the scope of this chapter. In intuitive terms, we can understand the above empirical results as follows: Shocks affecting a specific investment penalize CLA's concentration. Shocks involving several correlated investments penalize IVP's ignorance of the correlation structure. HRP provides better protection against both common and idiosyncratic shocks by finding a compromise between diversification across all investments and diversification across clusters of investments at multiple hierarchical levels. Figure 16.7 plots the time series of allocations for the first of the 10,000 runs.</p>"
            "<p>Appendix 16.A.4 provides the Python code that implements the above study. The reader can experiment with different parameter configurations and reach similar conclusions. In particular, HRP's out-of-sample outperformance becomes even</p>"
        )
    if stripped.startswith("Between the first and second rebalance"):
        return (
            "<p><strong>(a) IVP.</strong> Between the first and second rebalance, one investment receives an idiosyncratic shock, which increases its variance. IVP's response is to reduce the allocation to that investment, and spread that former exposure across all other investments. Between the fifth and sixth rebalance, two investments are affected by a common shock. IVP's response is the same. As a result, allocations among the seven unaffected investments grow over time, regardless of their correlation.</p>"
            "<p><strong>(b) HRP.</strong> HRP's response to the idiosyncratic shock is to reduce the allocation to the affected investment, and use that reduced amount to increase the allocation to a correlated investment that was unaffected. As a response to the common shock, HRP reduces allocation to the affected investments and increases allocation to uncorrelated ones (with lower variance).</p>"
            "<p><strong>(c) CLA.</strong> CLA allocations respond erratically to idiosyncratic and common shocks. If we had taken into account rebalancing costs, CLA's performance would have been very negative.</p>"
        )
    if stripped.startswith("lowest variance"):
        return ""
    if stripped.startswith("The methodology introduced in this chapter"):
        return (
            "<p>The methodology introduced in this chapter is flexible, scalable and admits multiple variations of the same ideas. Using the code provided, readers can research and evaluate what HRP configurations work best for their particular problem. For example, at stage 1 they can apply alternative definitions of "
            + math_inline(r"d_{i,j}")
            + ", "
            + math_inline(r"\tilde d_{i,j}")
            + " and "
            + math_inline(r"\dot d_{i,u}")
            + ", or different clustering algorithms, like biclustering; at stage 3, they can use different functions for "
            + math_inline(r"\tilde w_m")
            + " and "
            + math_inline(r"\alpha")
            + ", or alternative allocation constraints. Instead of carrying out a recursive bisection, stage 3 could also split allocations top-down using the clusters from stage 1.</p>"
            "<p>It is relatively straightforward to incorporate forecasted returns, Ledoit-Wolf shrinkage, and Black-Litterman-style views to this hierarchical approach. In fact, the inquisitive reader may have realized that, at its core, HRP is essentially a robust procedure to avoid matrix inversions, and the same ideas underlying HRP can be used to replace many econometric regression methods, notorious for their unstable outputs (like VAR or VECM). Figure 16.8 displays (a) a large correlation matrix of fixed income securities before and (b) after clustering, with over 2.1 million entries. Traditional optimization or econometric methods fail to recognize the hierarchical structure of financial Big Data, where the numerical instabilities defeat the benefits of the analysis, resulting in unreliable and detrimental outcomes.</p>"
        )
    if stripped.startswith("The methodology described in this chapter can be applied"):
        return "<p>The methodology described in this chapter can be applied to problems beyond optimization. For example, a PCA analysis of a large fixed income universe suffers the same drawbacks we described for CLA. Small-data techniques developed decades and centuries ago (factor models, regression analysis, econometrics) fail to recognize the hierarchical nature of financial big data.</p>"
    if stripped.startswith("of our findings, in which HRP"):
        return (
            "<p>Kolanovic et al. [2017] conducted a lengthy study of HRP, concluding that \"HRP delivers superior risk-adjusted returns. Whilst both the HRP and the MV portfolios deliver the highest returns, the HRP portfolios match with volatility targets much better than MV portfolios. We also run simulation studies to confirm the robustness of our findings, in which HRP consistently deliver a superior performance over MV and other risk-based strategies [...] HRP portfolios are truly diversified with a higher number of uncorrelated exposures, and less extreme weights and risk allocations.\"</p>"
            "<p>Raffinot [2017] concludes that \"empirical results indicate that hierarchical clustering based portfolios are robust, truly diversified and achieve statistically better risk-adjusted performances than commonly used portfolio optimization techniques.\"</p>"
        )
    if stripped.startswith("Exact analytical solutions can perform"):
        return (
            "<p>Exact analytical solutions can perform much worse than approximate ML solutions. Although mathematically correct, quadratic optimizers in general, and Markowitz's CLA in particular, are known to deliver generally unreliable solutions due to their instability, concentration, and underperformance. The root cause for these issues is that quadratic optimizers require the inversion of a covariance matrix. Markowitz's curse is that the more correlated investments are, the greater is the need for a diversified portfolio, and yet the greater are that portfolio's estimation errors.</p>"
            "<p>In this chapter, we have exposed a major source of quadratic optimizers' instability: A matrix of size "
            + math_inline("N")
            + " is associated with a complete graph with "
            + math_inline(r"\frac{1}{2}N(N-1)")
            + " edges. With so many edges connecting the nodes of the graph, weights are allowed to rebalance with complete freedom. This lack of hierarchical structure means that small estimation errors will lead to entirely different solutions. HRP replaces the covariance structure with a tree structure, accomplishing three goals: (1) Unlike traditional risk parity methods, it fully utilizes the information contained in the covariance matrix, (2) weights' stability is recovered and (3) the solution is intuitive by construction. The algorithm converges in deterministic logarithmic (best case) or linear (worst case) time.</p>"
            "<p>HRP is robust, visual, and flexible, allowing the user to introduce constraints or manipulate the tree structure without compromising the algorithm's search. These properties are derived from the fact that HRP does not require covariance invertibility. Indeed, HRP can compute a portfolio on an ill-degenerated or even a singular covariance matrix.</p>"
            "<p>This chapter focuses on a portfolio construction application; however, the reader will find other practical uses for making decisions under uncertainty, particularly in the presence of a nearly singular covariance matrix: capital allocation to portfolio managers, allocations across algorithmic strategies, bagging and boosting of machine learning signals, forecasts from random forests, replacement to unstable econometric models (VAR, VECM), etc.</p>"
            "<p>Of course, quadratic optimizers like CLA produce the minimum-variance portfolio in-sample (that is its objective function). Monte Carlo experiments show that HRP delivers lower out-of-sample variance than CLA or traditional risk parity methods (IVP). Since Bridgewater pioneered risk parity in the 1990s, some of the largest asset managers have launched funds that follow this approach, for combined assets in excess of $500 billion. Given their extensive use of leverage, these funds should benefit from adopting a more stable risk parity allocation method, thus achieving superior risk-adjusted returns and lower rebalance costs.</p>"
        )
    if stripped.startswith("Consider two real-valued vectors"):
        return (
            "<p>Consider two real-valued vectors "
            + math_inline("X,Y")
            + " of size "
            + math_inline("T")
            + ", and a correlation variable "
            + math_inline(r"\rho[x,y]")
            + ", with the only requirement that "
            + math_inline(r"\sigma[x,y]=\rho[x,y]\sigma[X]\sigma[Y]")
            + ", where "
            + math_inline(r"\sigma[x,y]")
            + " is the covariance between the two vectors, and "
            + math_inline(r"\sigma[\cdot]")
            + " is the standard deviation. Note that Pearson's is not the only correlation to satisfy these requirements.</p>"
            "<p>Let us prove that "
            + math_inline(r"d[x,y]=\sqrt{\frac{1}{2}(1-\rho[x,y])}")
            + " is a true metric. First, the Euclidean distance between the two vectors is "
            + math_inline(r"d_E[X,Y]=\sqrt{\sum_{t=1}^{T}(X_t-Y_t)^2}")
            + ". Second, we z-standardize those vectors as</p>"
            + math_display(r"x=\frac{X-\bar X}{\sigma[X]},\qquad y=\frac{Y-\bar Y}{\sigma[Y]}")
            + "<p>Consequently, "
            + math_inline(r"0\le\rho[x,y]=\rho[X,Y]")
            + ". Third, we derive the Euclidean distance "
            + math_inline(r"d_E[x,y]")
            + " as</p>"
            + math_display(r"d_E[x,y]=\sqrt{\sum_{t=1}^{T}(x_t-y_t)^2}=\sqrt{\sum_{t=1}^{T}x_t^2+\sum_{t=1}^{T}y_t^2-2\sum_{t=1}^{T}x_ty_t}")
            + math_display(r"d_E[x,y]=\sqrt{2T(1-\rho[x,y])}=2\sqrt{T}\,d[x,y]")
            + "<p>In other words, the distance "
            + math_inline(r"d[x,y]")
            + " is a linear multiple of the Euclidean distance between the vectors "
            + math_inline(r"\{X,Y\}")
            + " after z-standardization, hence it inherits the true-metric properties of the Euclidean distance.</p>"
            "<p>Similarly, we can prove that "
            + math_inline(r"d[x,y]=\sqrt{1-|\rho[x,y]|}")
            + " descends to a true metric on the "
            + math_inline(r"\mathbb{Z}/2\mathbb{Z}")
            + " quotient. In order to do that, we redefine "
            + math_inline(r"y=\frac{Y-\bar Y}{\sigma[Y]}\operatorname{sgn}[\rho[x,y]]")
            + ", where "
            + math_inline(r"\operatorname{sgn}[\cdot]")
            + " is the sign operator, so that "
            + math_inline(r"0\le\rho[x,y]=|\rho[x,y]|")
            + ". Then,</p>"
            + math_display(r"d_E[x,y]=\sqrt{2T(1-|\rho[x,y]|)}=\sqrt{2T}\,d[x,y]")
        )
    if stripped.startswith("Stage 3 (see Section 16.4.3) splits"):
        return (
            "<p>Stage 3 (see Section 16.4.3) splits a weight in inverse proportion to the subset's variance. We now prove that such allocation is optimal when the covariance matrix is diagonal. Consider the standard quadratic optimization problem of size "
            + math_inline("N")
            + ",</p>"
            + math_display(r"\min_{\omega}\omega^\prime V\omega\quad\text{s.t.}\quad \omega^\prime a=1")
        )
    if stripped.startswith("with solution"):
        return (
            "<p>with solution "
            + math_inline(r"\omega=\frac{V^{-1}a}{a^\prime V^{-1}a}")
            + ". For the characteristic vector "
            + math_inline(r"a=\mathbf{1}_N")
            + ", the solution is the minimum variance portfolio. If "
            + math_inline("V")
            + " is diagonal,</p>"
            + math_display(r"\omega_n=\frac{V_{n,n}^{-1}}{\sum_{i=1}^{N}V_{i,i}^{-1}}")
            + "<p>In the particular case of "
            + math_inline("N=2")
            + ",</p>"
            + math_display(r"\omega_1=\frac{1/V_{1,1}}{1/V_{1,1}+1/V_{2,2}}=1-\frac{V_{1,1}}{V_{1,1}+V_{2,2}}")
            + "<p>which is how stage 3 splits a weight between two bisections of a subset.</p>"
        )
    if stripped.startswith("Snippet 16.5 implements Monte Carlo"):
        return (
            chapter_16_appendix_heading("16.A.4 REPRODUCING THE MONTE CARLO EXPERIMENT")
            + "<p>Snippet 16.5 implements Monte Carlo experiments on three allocation methods: HRP, CLA, and IVP. All libraries are standard except for HRP, which is provided in Appendix 16.A.3, and CLA, which can be found in Bailey and López de Prado [2013]. The subroutine generateData simulates the correlated data, with two types of random shocks: common to various investments and specific to a single investment. There are two shocks of each type, one positive and one negative. The variables for the experiments are set as arguments of hrpMC. They were chosen arbitrarily, and the user can experiment with alternative combinations.</p>"
        )
    return None


def chapter_17_paragraph_html(text: str) -> str | None:
    stripped = text.strip()
    if stripped in {
        "ft",
        "t",
        "T",
        "i=2",
        "l=1",
        "Close price (after ETF trick)",
        "2 SADF",
        "( ) ∑ T",
        "t=𝜏",
        "Time (a)",
        "(b)",
        "SADFt (x-axis)",
        "gale.",
    }:
        return ""
    if stripped.startswith("In developing an ML-based investment strategy"):
        return "<p>In developing an ML-based investment strategy, we typically wish to bet when there is a confluence of factors whose predicted outcome offers a favorable risk-adjusted return. Structural breaks, like the transition from one market regime to another, are one example of such a confluence that is of particular interest. For instance, a mean-reverting pattern may give way to a momentum pattern. As this transition takes place, most market participants are caught off guard, and they will make costly mistakes. This sort of error is the basis for many profitable strategies, because the actors on the losing side will typically become aware of their mistake once it is too late. Before they accept their losses, they will act irrationally, try to hold the position, and hope for a comeback. Sometimes they will even increase a losing position, in desperation. Eventually they will be forced to stop loss or stop out. Structural breaks offer some of the best risk/rewards. In this chapter, we will review some methods that measure the likelihood of structural breaks, so that informative features can be built upon them.</p>"
    if stripped.startswith("This test was proposed by Brown"):
        return (
            "<p>This test was proposed by Brown, Durbin and Evans [1975]. Let us assume that at every observation "
            + math_inline(r"t=1,\ldots,T")
            + ", we count with an array of features "
            + math_inline("x_t")
            + " predictive of a value "
            + math_inline("y_t")
            + ". Matrix "
            + math_inline("X_t")
            + " is composed of the time series of features "
            + math_inline(r"t\le T")
            + ", "
            + math_inline(r"\{x_i\}_{i=1,\ldots,t}")
            + ". These authors propose that we compute recursive least squares (RLS) estimates of "
            + math_inline(r"\beta")
            + ", based on the specification</p>"
        )
    if stripped.startswith("which is fit on subsamples"):
        return (
            "<p>which is fit on subsamples "
            + math_inline(r"([1,k+1],[1,k+2],\ldots,[1,T])")
            + ", giving "
            + math_inline("T-k")
            + " least squares estimates "
            + math_inline(r"(\hat{\beta}_{k+1},\ldots,\hat{\beta}_{T})")
            + ". We can compute the standardized 1-step ahead recursive residuals as</p>"
        )
    if stripped.startswith("St = j=k+1"):
        return math_display(r"S_t=\frac{\sum_{j=k+1}^{t}\hat{\omega}_j}{\hat{\sigma}_{\omega}}")
    if stripped.startswith("Under the null hypothesis that 𝛽 is some constant"):
        return (
            "<p>Under the null hypothesis that "
            + math_inline(r"\beta")
            + " is some constant value, "
            + math_inline(r"H_0:\beta_t=\beta")
            + ", then "
            + math_inline(r"S_t\sim N[0,t-k-1]")
            + ". One caveat of this procedure is that the starting point is chosen arbitrarily, and results may be inconsistent due to that.</p>"
        )
    if stripped.startswith("This test follows Homm and Breitung"):
        return (
            "<p>This test follows Homm and Breitung [2012]. It simplifies the previous method by dropping "
            + math_inline(r"\{x_t\}_{t=1,\ldots,T}")
            + ", and assuming that "
            + math_inline(r"H_0:\beta_t=0")
            + ", that is, we forecast no change "
            + math_inline(r"(\mathbb{E}_{t-1}[\Delta y_t]=0)")
            + ". This will allow us to work directly with "
            + math_inline("y_t")
            + " levels, hence reducing the computational burden. We compute the standardized departure of log-price "
            + math_inline("y_t")
            + " relative to the log-price at "
            + math_inline("y_n")
            + ", "
            + math_inline("t>n")
            + ", as</p>"
        )
    if stripped.startswith("Under the null hypothesis H_0: 𝛽t = 0") or stripped.startswith("Under the null hypothesis H0"):
        return (
            "<p>Under the null hypothesis "
            + math_inline(r"H_0:\beta_t=0")
            + ", then "
            + math_inline(r"S_{n,t}\sim N[0,1]")
            + ". The time-dependent critical value for the one-sided test is</p>"
        )
    if stripped.startswith("These authors derived via Monte Carlo"):
        return (
            "<p>These authors derived via Monte Carlo that "
            + math_inline(r"b_{0.05}=4.6")
            + ". One disadvantage of this method is that the reference level "
            + math_inline("y_n")
            + " is set somewhat arbitrarily. To overcome this pitfall, we could estimate "
            + math_inline(r"S_{n,t}")
            + " on a series of backward-shifting windows "
            + math_inline(r"n\in[1,t-1]")
            + ", and pick "
            + math_inline(r"S_t=\sup_{n\in[1,t-1]}\{S_{n,t}\}")
            + ".</p>"
        )
    if stripped.startswith("where 𝜀t is white noise"):
        return (
            "<p>where "
            + math_inline(r"\varepsilon_t")
            + " is white noise. The null hypothesis is that "
            + math_inline("y_t")
            + " follows a random walk, "
            + math_inline(r"H_0:\rho=1")
            + ", and the alternative hypothesis is that "
            + math_inline("y_t")
            + " starts as a random walk but changes at time "
            + math_inline(r"\tau^*T")
            + ", where "
            + math_inline(r"\tau^*\in(0,1)")
            + ", into an explosive process:</p>"
        )
    if stripped.startswith("H1 : yt ="):
        return ""
    if stripped.startswith("At time T we can test for a switch"):
        return (
            "<p>At time "
            + math_inline("T")
            + " we can test for a switch (from random walk to explosive process) having taken place at time "
            + math_inline(r"\tau^*T")
            + " (break date). In order to test this hypothesis, we fit the following specification,</p>"
        )
    if stripped.startswith("where Dt [𝜏 ∗ ]"):
        return (
            "<p>where "
            + math_inline(r"D_t[\tau^*]")
            + " is a dummy variable that takes zero value if "
            + math_inline(r"t<\tau^*T")
            + ", and takes the value one if "
            + math_inline(r"t\ge\tau^*T")
            + ". Then, the null hypothesis "
            + math_inline(r"H_0:\delta=0")
            + " is tested against the one-sided alternative "
            + math_inline(r"H_1:\delta>0")
            + ":</p>"
        )
    if stripped.startswith("The main drawback of this method"):
        return (
            "<p>The main drawback of this method is that "
            + math_inline(r"\tau^*")
            + " is unknown. To address this issue, Andrews [1993] proposed a new test where all possible "
            + math_inline(r"\tau^*")
            + " are tried, within some interval "
            + math_inline(r"\tau^*\in[\tau_0,1-\tau_0]")
            + ". As Breitung [2014] explains, we should leave out some of the possible "
            + math_inline(r"\tau^*")
            + " at the beginning and end of the sample, to ensure that either regime is fitted with enough observations (there must be enough zeros and enough ones in "
            + math_inline(r"D_t[\tau^*]")
            + "). The test statistic for an unknown "
            + math_inline(r"\tau^*")
            + " is the maximum of all "
            + math_inline(r"T(1-2\tau_0)")
            + " values of "
            + math_inline(r"DFC_{\tau^*}")
            + ".</p>"
        )
    if stripped.startswith("Another drawback of Chow"):
        return (
            "<p>Another drawback of Chow's approach is that it assumes that there is only one break date "
            + math_inline(r"\tau^*T")
            + ", and that the bubble runs up to the end of the sample (there is no switch back to a random walk). For situations where three or more regimes (random walk "
            + math_inline(r"\to")
            + " bubble "
            + math_inline(r"\to")
            + " random walk "
            + math_inline(r"\ldots")
            + ") exist, we need to discuss the Supremum Augmented Dickey-Fuller (SADF) test.</p>"
        )
    if stripped.startswith("where we test for H_0: 𝛽 ≤ 0") or stripped.startswith("where we test for H0"):
        return "<p>where we test for " + math_inline(r"H_0:\beta\le0") + ", " + math_inline(r"H_1:\beta>0") + ". Inspired by Andrews [1993], Phillips and Yu [2011] and Phillips, Wu and Yu [2011] proposed the Supremum Augmented Dickey-Fuller test (SADF).</p>"
    if stripped.startswith("Dickey-Fuller test (SADF)"):
        return "<p>SADF fits the above regression at each end point " + math_inline("t") + " with backwards expanding start points, then computes</p>"
    if stripped.startswith("where 𝛽̂t0 ,t is estimated"):
        return (
            "<p>where "
            + math_inline(r"\hat{\beta}_{t_0,t}")
            + " is estimated on a sample that starts at "
            + math_inline("t_0")
            + " and ends at "
            + math_inline("t")
            + ", "
            + math_inline(r"\tau")
            + " is the minimum sample length used in the analysis, "
            + math_inline("t_0")
            + " is the left bound of the backwards expanding window, and "
            + math_inline(r"t=\tau,\ldots,T")
            + ". For the estimation of "
            + math_inline(r"SADF_t")
            + ", the right side of the window is fixed at "
            + math_inline("t")
            + ". The standard ADF test is a special case of "
            + math_inline(r"SADF_t")
            + ", where "
            + math_inline(r"\tau=t-1")
            + ". There are two critical differences between "
            + math_inline(r"SADF_t")
            + " and "
            + math_inline("SDFC")
            + ": First, "
            + math_inline(r"SADF_t")
            + " is computed at each "
            + math_inline(r"t\in[\tau,T]")
            + ", whereas SDFC is computed only at "
            + math_inline("T")
            + ". Second, instead of introducing a dummy variable, SADF recursively expands the beginning of the sample ("
            + math_inline(r"t_0\in[1,t-\tau]")
            + "). By trying all combinations of a nested double loop on "
            + math_inline(r"(t_0,t)")
            + ", SADF does not assume a known number of regime switches or break dates. Figure 17.1 displays the series of E-mini S&P 500 futures prices after applying the ETF trick (Chapter 2, Section 2.4.1), as well as the SADF derived from that price series. The SADF line spikes when prices exhibit a bubble-like behavior, and returns to low levels when the bubble bursts. In the following sections, we will discuss some enhancements to Phillips' original SADF method.</p>"
        )
    if stripped.startswith("For raw prices {yt }"):
        return (
            "<p>For raw prices "
            + math_inline(r"\{y_t\}")
            + ", if ADF's null hypothesis is rejected, it means that prices are stationary, with finite variance. The implication is that returns "
            + math_inline(r"\frac{y_t}{y_{t-1}}-1")
            + " are not time invariant, for returns' volatility must decrease as prices rise and increase as prices fall in order to keep the price variance constant. When we run ADF on raw prices, we assume that returns' variance is not invariant to price levels. If returns variance happens to be invariant to price levels, the model will be structurally heteroscedastic.</p><p>In contrast, if we work with log prices, the ADF specification will state that</p>"
        )
    if stripped.startswith("invariant, for returns"):
        return ""
    if stripped.startswith("Let us make a change of variable"):
        return "<p>Let us make a change of variable, " + math_inline(r"x_t=ky_t") + ". Now, " + math_inline(r"\log[x_t]=\log[k]+\log[y_t]") + ", and the ADF specification will state that</p>"
    if stripped.startswith("Under this alternative specification based on log prices"):
        return "<p>Under this alternative specification based on log prices, price levels condition returns' mean, not returns' volatility. The difference may not matter in practice for small samples, where " + math_inline(r"k\approx1") + ", but SADF runs regressions across decades and bubbles produce levels that are significantly different between regimes (" + math_inline(r"k\ne1") + ").</p>"
    if stripped.startswith("The algorithm runs in"):
        return "<p>The algorithm runs in " + math_inline(r"\mathcal{O}(n^2)") + ", as the number of ADF tests that SADF requires for a total sample length " + math_inline("T") + " is</p>"
    if stripped.startswith("Consider a matrix representation"):
        return (
            "<p>Consider a matrix representation of the ADF specification, where "
            + math_inline(r"X\in\mathbb{R}^{T\times N}")
            + " and "
            + math_inline(r"y\in\mathbb{R}^{T\times1}")
            + ". Solving a single ADF regression involves the floating point operations (FLOPs) listed in Table 17.1.</p>"
            "<p>This gives a total of "
            + math_inline(r"f(N,T)=N^3+N^2(2T+3)+N(4T-1)+2T+2")
            + " FLOPs per ADF estimate. A single SADF update requires "
            + math_inline(r"g(N,T,\tau)=\sum_{t=\tau}^{T}f(N,t)+T-\tau")
            + " FLOPs ("
            + math_inline(r"T-\tau")
            + " operations to find the maximum ADF stat), and the estimation of a full SADF series requires "
            + math_inline(r"\sum_{t=\tau}^{T}g(N,t,\tau)")
            + ".</p>"
            "<p>Consider a dollar bar series on E-mini S&amp;P 500 futures. For "
            + math_inline(r"(T,N)=(356631,3)")
            + ", an ADF estimate requires 11,412,245 FLOPs, and a SADF update requires 2,034,979,648,799 operations (roughly "
            + math_inline("2.035")
            + " TFLOPs). A full SADF time series requires 241,910,974,617,448,672 operations (roughly 242 PFLOPs). This number will increase quickly as "
            + math_inline("T")
            + " continues to grow. This estimate also excludes notoriously expensive operations like alignment, data pre-processing, I/O jobs, and related work. Needless to say, this algorithm's double loop requires a large number of operations. An HPC cluster running an efficiently parallelized implementation of the algorithm may be needed to estimate the SADF series within a reasonable amount of time. Chapter 20 presents some parallelization strategies useful in these situations.</p>"
        )
    if stripped.startswith("per ADF estimate") or stripped.startswith("SADF series requires"):
        return ""
    if stripped.startswith("Consider the zero-lag specification"):
        return (
            "<p>Consider the zero-lag specification on log prices, "
            + math_inline(r"\Delta\log[y_t]=\alpha+\beta\log[y_{t-1}]+\varepsilon_t")
            + ". This can be rewritten as "
            + math_inline(r"\log[\tilde y_t]=(1+\beta)\log[\tilde y_{t-1}]+\varepsilon_t")
            + ", where "
            + math_inline(r"\log[\tilde y_t]=\log[y_t]+\frac{\alpha}{\beta}")
            + ". Rolling back "
            + math_inline("t")
            + " discrete steps, we obtain "
            + math_inline(r"\mathbb{E}[\log[\tilde y_t]]=(1+\beta)^t\log[\tilde y_0]")
            + ", or "
            + math_inline(r"\mathbb{E}[\log[y_t]]=-\frac{\alpha}{\beta}+(1+\beta)^t\left(\log[y_0]+\frac{\alpha}{\beta}\right)")
            + ". The index "
            + math_inline("t")
            + " can be reset at a given time, to project the future trajectory of "
            + math_inline(r"y_0\to y_t")
            + " after the next "
            + math_inline("t")
            + " steps. This reveals the conditions that characterize the three states for this dynamic system:</p>"
        )
    if stripped.startswith("SADF takes the supremum"):
        return (
            "<p>SADF takes the supremum of a series on t-values, "
            + math_inline(r"SADF_t=\sup_{t_0\in[1,t-\tau]}\{ADF_{t_0,t}\}")
            + ". Selecting the extreme value introduces some robustness problems, where SADF estimates could vary significantly depending on the sampling frequency and the specific timestamps of the samples. A more robust estimator of ADF extrema would be the following: First, let "
            + math_inline(r"s_t=\{ADF_{t_0,t}\}_{t_0\in[1,t-\tau]}")
            + ". Second, we define "
            + math_inline(r"Q_{t,q}=Q[s_t,q]")
            + " the "
            + math_inline("q")
            + " quantile of "
            + math_inline("s_t")
            + ", as a measure of centrality of high ADF values, where "
            + math_inline(r"q\in[0,1]")
            + ". Third, we define "
            + math_inline(r"\dot Q_{t,q,v}=Q_{t,q+v}-Q_{t,q-v}")
            + ", with "
            + math_inline(r"0<v\le\min\{q,1-q\}")
            + ", as a measure of dispersion of high ADF values. For example, we could set "
            + math_inline(r"q=0.95")
            + " and "
            + math_inline(r"v=0.025")
            + ".</p>"
        )
    if stripped.startswith("that SADF is merely"):
        return "<p>Note that SADF is merely a particular case of QADF, where " + math_inline(r"SADF_t=Q_{t,1}") + " and " + math_inline(r"\dot Q_{t,q,v}") + " is not defined because " + math_inline("q=1") + ".</p>"
    if stripped.startswith("Alternatively, we can address concerns"):
        return "<p>Alternatively, we can address concerns on SADF robustness by computing conditional moments. Let " + math_inline(r"f[x]") + " be the probability distribution function of " + math_inline(r"s_t=\{ADF_{t_0,t}\}_{t_0\in[1,t-\tau]}") + ", with " + math_inline(r"x\in s_t") + ". Then, we define</p>" + math_display(r"C_{t,q}=K^{-1}\int_{Q_{t,q}}^{\infty}x f[x]\,dx,\qquad \dot C_{t,q}=\sqrt{K^{-1}\int_{Q_{t,q}}^{\infty}(x-C_{t,q})^2 f[x]\,dx}") + "<p>as measures of centrality and dispersion of high ADF values, with regularization constant " + math_inline(r"K=\int_{Q_{t,q}}^{\infty}f[x]\,dx") + ". For example, we could use " + math_inline(r"q=0.95") + ".</p>"
    if stripped.startswith("{ADFt0 ,t }"):
        return ""
    if stripped.startswith("By construction") or stripped.startswith("sure of centrality"):
        return "<p>By construction, " + math_inline(r"C_{t,q}\le SADF_t") + ". A scatter plot of " + math_inline(r"SADF_t") + " against " + math_inline(r"C_{t,q}") + " shows that lower boundary, as an ascending line with approximately unit gradient (see Figure 17.2). When SADF grows beyond " + math_inline("-1.5") + ", we can appreciate some horizontal trajectories, consistent with a sudden widening of the right fat tail in " + math_inline("s_t") + ". In other words, " + math_inline(r"(SADF_t-C_{t,q})/\dot C_{t,q}") + " can reach significantly large values even if " + math_inline(r"C_{t,q}") + " is relatively small, because " + math_inline(r"SADF_t") + " is sensitive to outliers.</p><p>Figure 17.3(a) plots " + math_inline(r"(SADF_t-C_{t,q})/\dot C_{t,q}") + " for the E-mini S&P 500 futures prices over time. Figure 17.3(b) is the scatter-plot of " + math_inline(r"(SADF_t-C_{t,q})/\dot C_{t,q}") + " against " + math_inline(r"SADF_t") + ", computed on the E-mini S&P 500 futures prices. It shows evidence that outliers in " + math_inline("s_t") + " bias " + math_inline(r"SADF_t") + " upwards.</p>"
    if stripped.startswith("This section presents an implementation"):
        return "<p>This section presents an implementation of the SADF algorithm. The purpose of this code is not to estimate SADF quickly, but to clarify the steps involved in its estimation. Snippet 17.1 lists SADF's inner loop. That is the part that estimates " + math_inline(r"SADF_t=\sup_{t_0\in[1,t-\tau]}\left\{\frac{\hat{\beta}_{t_0,t}}{\hat{\sigma}_{\beta_{t_0,t}}}\right\}") + ", which is the backshifting component of the algorithm. The outer loop (not shown here) repeats this calculation for an advancing " + math_inline("t") + ", " + math_inline(r"\{SADF_t\}_{t=1,\ldots,T}") + ". The arguments are:</p>"
    if stripped.startswith("loop (not shown here)") or stripped == "t0 ∈ [1,t−𝜏] βt ,t":
        return ""
    if stripped.startswith("Snippet 17.2 lists function getXY"):
        return "<p>Snippet 17.2 lists function <code>getYX</code>, which prepares the numpy objects needed to conduct the recursive tests.</p>"
    if stripped.startswith("In this section we will introduce explosiveness tests"):
        return "<p>In this section we will introduce explosiveness tests that do not rely on the standard ADF specification. Consider a process that is either a sub- or super-martingale. Given some observations " + math_inline(r"\{y_t\}") + ", we would like to test for the existence of an explosive time trend, " + math_inline(r"H_0:\beta=0") + ", " + math_inline(r"H_1:\beta\ne0") + ", under alternative specifications:</p>"
    if stripped.startswith("some observations"):
        return ""
    if stripped.startswith("yt = 𝛼e𝛽t"):
        return math_display(r"y_t=\alpha e^{\beta t}\eta_t,\quad \log[\eta_t]=\xi_t\Rightarrow\log[y_t]=\log[\alpha]+\beta t+\xi_t")
    if stripped.startswith("yt = 𝛼t𝛽"):
        return math_display(r"y_t=\alpha t^\beta\eta_t,\quad \log[\eta_t]=\xi_t\Rightarrow\log[y_t]=\log[\alpha]+\beta\log[t]+\xi_t")
    if stripped.startswith("Similar to SADF"):
        return "<p>Similar to SADF, we fit any of these specifications to each end point " + math_inline(r"t=\tau,\ldots,T") + ", with backwards expanding start points, then compute</p>" + math_display(r"SMT_t=\sup_{t_0\in[1,t-\tau]}\left\{\frac{|\hat{\beta}_{t_0,t}|}{\hat{\sigma}_{\beta_{t_0,t}}}\right\}")
    if stripped.startswith("The reason for the absolute value"):
        return "<p>The reason for the absolute value is that we are equally interested in explosive growth and collapse. In the simple regression case (Greene [2008], p. 48), the variance of " + math_inline(r"\beta") + " is</p>" + math_display(r"\hat{\sigma}_{\beta}^{2}=\frac{\hat{\sigma}_{\varepsilon}^{2}}{\hat{\sigma}_{xx}^{2}(t-t_0)}") + "<p>hence " + math_inline(r"\lim_{t\to\infty}\hat{\sigma}_{\beta_{t_0,t}}=0") + ". The same result is generalizable to the multivariate linear regression case (Greene [2008], pp. 51-52). The " + math_inline(r"\hat{\sigma}_{\beta}^{2}") + " of a weak long-run bubble may be smaller than the " + math_inline(r"\hat{\sigma}_{\beta}^{2}") + " of a strong short-run bubble, hence biasing the method towards long-run bubbles. To correct for this bias, we can penalize large sample lengths by determining the coefficient " + math_inline(r"\varphi\in[0,1]") + " that yields best explosiveness signals.</p>" + math_display(r"SMT_t=\sup_{t_0\in[1,t-\tau]}\left\{\frac{|\hat{\beta}_{t_0,t}|}{\hat{\sigma}_{\beta_{t_0,t}}(t-t_0)^\varphi}\right\}")
    if stripped.startswith("𝜀 ) , hence"):
        return ""
    if stripped.startswith("For instance, when 𝜑 = 0.5"):
        return "<p>For instance, when " + math_inline(r"\varphi=0.5") + ", we compensate for the lower " + math_inline(r"\hat{\sigma}_{\beta_{t_0,t}}") + " associated with longer sample lengths, in the simple regression case. For " + math_inline(r"\varphi\to0") + ", " + math_inline(r"SMT_t") + " will exhibit longer trends, as that compensation wanes and long-run bubbles mask short-run bubbles. For " + math_inline(r"\varphi\to1") + ", " + math_inline(r"SMT_t") + " becomes noisier, because more short-run bubbles are selected over long-run bubbles. Consequently, this is a natural way to adjust the explosiveness signal, so that it filters opportunities targeting a particular holding period. The features used by the ML algorithm may include " + math_inline(r"SMT_t") + " estimated from a wide range of " + math_inline(r"\varphi") + " values.</p>"
    if stripped.startswith("signal, so that"):
        return ""
    return None


def chapter_18_paragraph_html(text: str) -> str | None:
    stripped = text.strip()
    suppress_exact = {
        "j+l",
        "Lin 1 lim =",
        "and a number of matches k ≥ 1, the sliding-window LZ estimator Ĥ n,k = Ĥ n,k [x−n+1",
        "is defined by",
        "k n Ĥ n,k =",
        "n i Ĥ n =",
        "k",
        "Hn,k = k i=1 Lin",
        "H n i=2 Li",
        "( n )1∕q",
        "i=1",
        "( n )1∕",
        "q",
        "N",
        "PIN =",
        "Degree",
        "Degree 15",
        "Degree 20",
        "(a)",
        "(b)",
        "(c)",
        "(d)",
        "log effective number",
    }
    if stripped in suppress_exact:
        return ""
    if stripped.startswith("None count") or stripped.startswith("sages of length 100") or stripped.startswith("ings, on messages"):
        return ""
    if stripped.startswith("In this section we will review a few concepts"):
        return (
            "<p>In this section we will review a few concepts from information theory that will be useful in the remainder of the chapter. The reader can find a complete exposition in MacKay [2003]. The father of information theory, Claude Shannon, defined entropy as the average amount of information (over long messages) produced by a stationary source of data. It is the smallest number of bits per character required to describe the message in a uniquely decodable way. Mathematically, Shannon [1948] defined the entropy of a discrete random variable "
            + math_inline("X")
            + " with possible values "
            + math_inline(r"x\in A")
            + " as</p>"
        )
    if stripped.startswith("with 0 ≤ H[X]"):
        return (
            "<p>with "
            + math_inline(r"0\le H[X]\le \log_2[\|A\|]")
            + ", where "
            + math_inline(r"p[x]")
            + " is the probability of "
            + math_inline("x")
            + "; "
            + math_inline(r"H[X]=0\Leftrightarrow\exists x\mid p[x]=1")
            + "; "
            + math_inline(r"H[X]=\log_2[\|A\|]\Leftrightarrow p[x]=1/\|A\|")
            + " for all "
            + math_inline("x")
            + "; and "
            + math_inline(r"\|A\|")
            + " is the size of the set "
            + math_inline("A")
            + ". This can be interpreted as the probability weighted average of informational content in "
            + math_inline("X")
            + ", where the bits of information are measured as "
            + math_inline(r"\log_2\frac{1}{p[x]}")
            + ". The rationale for measuring information this way comes from the observation that low-probability outcomes reveal more information than high-probability outcomes. In other words, we learn when something unexpected happens. Similarly, redundancy is defined as</p>"
        )
    if stripped.startswith("with 0 ≤ R[X]"):
        return (
            "<p>with "
            + math_inline(r"0\le R[X]\le1")
            + ". Kolmogorov [1965] formalized the connection between redundancy and complexity of a Markov information source. The mutual information between two variables is defined as the Kullback-Leibler divergence from the joint probability density to the product of the marginal probability densities.</p>"
        )
    if stripped.startswith("Given a data sequence x1n"):
        return (
            "<p>Given a data sequence "
            + math_inline(r"x_1^n")
            + ", comprising the string of values starting in position 1 and ending in position "
            + math_inline("n")
            + ", we can form a dictionary of all words of length "
            + math_inline(r"w<n")
            + " in that sequence, "
            + math_inline(r"A^w")
            + ". Consider an arbitrary word "
            + math_inline(r"y_1^w\in A^w")
            + " of length "
            + math_inline("w")
            + ". We denote "
            + math_inline(r"\hat p_w[y_1^w]")
            + " the empirical probability of the word "
            + math_inline(r"y_1^w")
            + " in "
            + math_inline(r"x_1^n")
            + ", which means that "
            + math_inline(r"\hat p_w[y_1^w]")
            + " is the frequency with which "
            + math_inline(r"y_1^w")
            + " appears in "
            + math_inline(r"x_1^n")
            + ".</p>"
        )
    if stripped.startswith("In this section we will follow") and "Given a data sequence" in stripped:
        return (
            "<p>In this section we will follow the exposition of entropy's maximum likelihood estimator in Gao et al. [2008]. The nomenclature may seem a bit peculiar at first (no pun intended), but once you become familiar with it you will find it convenient. Given a data sequence "
            + math_inline(r"x_1^n")
            + ", comprising the string of values starting in position 1 and ending in position "
            + math_inline("n")
            + ", we can form a dictionary of all words of length "
            + math_inline(r"w<n")
            + " in that sequence, "
            + math_inline(r"A^w")
            + ". Consider an arbitrary word "
            + math_inline(r"y_1^w\in A^w")
            + " of length "
            + math_inline("w")
            + ". We denote "
            + math_inline(r"\hat p_w[y_1^w]")
            + " the empirical probability of the word "
            + math_inline(r"y_1^w")
            + " in "
            + math_inline(r"x_1^n")
            + ", which means that "
            + math_inline(r"\hat p_w[y_1^w]")
            + " is the frequency with which "
            + math_inline(r"y_1^w")
            + " appears in "
            + math_inline(r"x_1^n")
            + ".</p>"
        )
    if stripped.startswith("∈ Aw of length") or stripped.startswith("probability of the word"):
        return ""
    if stripped.startswith("yw appears in x1n"):
        return "<p>Assuming that the data is generated by a stationary and ergodic process, then the law of large numbers guarantees that, for a fixed " + math_inline("w") + " and large " + math_inline("n") + ", the empirical distribution " + math_inline(r"\hat p_w") + " will be close to the true distribution " + math_inline(r"p_w") + ". Under these circumstances, a natural estimator for the entropy rate (i.e., average entropy per bit) is</p>"
    if stripped.startswith("Since the empirical distribution"):
        return "<p>Since the empirical distribution is also the maximum likelihood estimate of the true distribution, this is also often referred to as the maximum likelihood entropy estimator. The value " + math_inline("w") + " should be large enough for " + math_inline(r"\hat H_{n,w}") + " to be acceptably close to the true entropy " + math_inline("H") + ". The value of " + math_inline("n") + " needs to be much larger than " + math_inline("w") + ", so that the empirical distribution of order " + math_inline("w") + " is close to the true distribution. Snippet 18.1 implements the plug-in entropy estimator.</p>"
    if stripped.startswith("Kontoyiannis [1998] attempts"):
        return "<p>Kontoyiannis [1998] attempts to make a more efficient use of the information available in a message. What follows is a faithful summary of the exposition in Gao et al. [2008]. We will reproduce the steps in that paper, while complementing them with code snippets that implement their ideas. Let us define " + math_inline(r"L_i^n") + " as 1 plus the length of the longest match found in the " + math_inline("n") + " bits prior to " + math_inline("i") + ",</p>"
    if stripped.startswith("Entropy can be interpreted as a measure of complexity"):
        return "<p>Entropy can be interpreted as a measure of complexity. A complex sequence contains more information than a regular (predictable) sequence. The Lempel-Ziv (LZ) algorithm efficiently decomposes a message into non-redundant substrings (Ziv and Lempel [1978]). We can estimate the compression rate of a message as a function of the number of items in a Lempel-Ziv dictionary relative to the length of the message. The intuition here is that complex messages have high entropy, which will require large dictionaries relative to the length of the string to be transmitted. Snippet 18.2 shows an implementation of the LZ compression algorithm.</p>"
    if stripped.startswith("algorithm efficiently decomposes"):
        return ""
    if stripped.startswith("Snippet 18.3 implements"):
        return "<p>Snippet 18.3 implements the algorithm that determines the length of the longest match. A few notes worth mentioning:</p>"
    if stripped.startswith("of the window.") or stripped.startswith("cannot start at i."):
        return ""
    if stripped.startswith("Kontoyiannis uses this result"):
        return (
            "<p>Kontoyiannis uses this result to estimate Shannon's entropy rate. He estimates the average of "
            + math_inline(r"L_i^n/\log_2[n]")
            + ", and uses the reciprocal of that average to estimate "
            + math_inline("H")
            + ". The general intuition is, as we increase the available history, we expect that messages with high entropy will produce relatively shorter non-redundant substrings. In contrast, messages with low entropy will produce relatively longer non-redundant substrings as we parse through the message.</p>"
            "<p>Given a data realization "
            + math_inline(r"x_{-\infty}^{\infty}")
            + ", a window length "
            + math_inline(r"n\ge1")
            + ", and a number of matches "
            + math_inline(r"k\ge1")
            + ", the sliding-window LZ estimator "
            + math_inline(r"\hat H_{n,k}=\hat H_{n,k}[x_{-n+1}^{n+k-1}]")
            + " is defined by</p>"
            + math_display(r"\hat{H}_{n,k}=\left[\frac{1}{k}\sum_{i=1}^{k}\frac{L_i^n}{\log_2[n]}\right]^{-1}")
            + "<p>Similarly, the increasing-window LZ estimator "
            + math_inline(r"\hat H_n=\hat H_n[x_0^{2n-1}]")
            + " is defined by</p>"
            + math_display(r"\hat{H}_{n}=\left[\frac{1}{n}\sum_{i=2}^{n}\frac{L_i^i}{\log_2[i]}\right]^{-1}")
        )
    if stripped.startswith("Similarly, the increasing"):
        return ""
    if stripped.startswith("The window size n is constant"):
        return (
            "<p>The window size "
            + math_inline("n")
            + " is constant when computing "
            + math_inline(r"\hat H_{n,k}")
            + ", thus "
            + math_inline(r"L_i^n")
            + ". However, when computing "
            + math_inline(r"\hat H_n")
            + ", the window size increases with "
            + math_inline("i")
            + ", thus "
            + math_inline(r"L_i^i")
            + ", with "
            + math_inline(r"n=N/2")
            + ". In this expanding-window case the length of the message "
            + math_inline("N")
            + " should be an even number to ensure that all bits are parsed (recall that "
            + math_inline("x_i")
            + " is at the center, so for an odd-length message the last bit would not be read).</p>"
        )
    if stripped.startswith("expanding window case"):
        return (
            "<p>The above expressions have been derived under the assumptions of stationarity, ergodicity, finite-valued observations, and the Doeblin condition. Intuitively, this condition requires that, after a finite number of steps "
            + math_inline("r")
            + ", no matter what has occurred before, anything can happen with positive probability. It turns out that this Doeblin condition can be avoided altogether if we consider a modified version of the above estimators:</p>"
            + math_display(r"\tilde{H}_{n,k}=\frac{1}{k}\sum_{i=1}^{k}\frac{\log_2[n]}{L_i^n}")
            + math_display(r"\tilde{H}_{n}=\frac{1}{n}\sum_{i=2}^{n}\frac{\log_2[i]}{L_i^i}")
        )
    if stripped.startswith("One practical question"):
        return (
            "<p>One practical question when estimating "
            + math_inline(r"\tilde H_{n,k}")
            + " is how to determine the window size "
            + math_inline("n")
            + ". Gao et al. [2008] argue that "
            + math_inline(r"k+n=N")
            + " should be approximately equal to the message length. Considering that the bias of "
            + math_inline(r"L_i^n")
            + " is of order "
            + math_inline(r"\mathcal{O}[1/\log_2[n]]")
            + " and the variance of "
            + math_inline(r"L_i^n")
            + " is order "
            + math_inline(r"\mathcal{O}[1/k]")
            + ", the bias/variance trade-off is balanced at around "
            + math_inline(r"k\approx\mathcal{O}[(\log_2[n])^2]")
            + ". That is, "
            + math_inline("n")
            + " could be chosen such that "
            + math_inline(r"N\approx n+(\log_2[n])^2")
            + ". For example, for "
            + math_inline(r"N=2^8")
            + ", a balanced bias/variance window size would be "
            + math_inline(r"n\approx198")
            + ", in which case "
            + math_inline(r"k\approx58")
            + ". Kontoyiannis [1998] proved that "
            + math_inline(r"\hat H[X]")
            + " converges to Shannon's entropy rate with probability 1 as "
            + math_inline("n")
            + " approaches infinity. Snippet 18.4 implements the ideas discussed in Gao et al. [2008], which improve on Kontoyiannis [1997] by looking for the maximum redundancy between two substrings of the same size.</p>"
        )
    if stripped.startswith("As an alternative approach"):
        return (
            "<p>As an alternative approach, rather than fixing the number of codes, we could let the price stream determine the actual dictionary. Suppose we fix a discretization step, "
            + math_inline(r"\sigma")
            + ". Then, we assign the value 0 to "
            + math_inline(r"r_t\in[\min\{r\},\min\{r\}+\sigma)")
            + ", 1 to "
            + math_inline(r"r_t\in[\min\{r\}+\sigma,\min\{r\}+2\sigma)")
            + ", and so on until every observation has been encoded with a total of "
            + math_inline(r"\left\lceil\frac{\max\{r\}-\min\{r\}}{\sigma}\right\rceil")
            + " codes, where "
            + math_inline(r"\lceil\cdot\rceil")
            + " is the ceiling function. Unlike quantile encoding, now each code covers the same fraction of "
            + math_inline(r"r_t")
            + "'s range. Because codes are not uniformly distributed, entropy readings will tend to be smaller than in quantile encoding on average; however, the appearance of a rare code will cause spikes in entropy readings.</p>"
        )
    if stripped.startswith("codes, where ceil") or stripped.startswith("encoding on average"):
        return ""
    if stripped.startswith("Estimating entropy requires the encoding"):
        return "<p>Estimating entropy requires the encoding of a message. In this section we will review a few encoding schemes used in the literature, which are based on returns. Although not discussed in what follows, it is advisable to encode information from fractionally (rather than integer) differentiated series (Chapter 4), as they still contain some memory.</p>"
    if stripped.startswith("not discussed in what follows"):
        return ""
    if stripped.startswith("Entropy rate estimation requires"):
        return (
            "<p>Entropy rate estimation requires the discretization of a continuous variable, so that each value can be assigned a code from a finite alphabet. For example, a stream of returns "
            + math_inline("r_t")
            + " can be encoded according to the sign, 1 for "
            + math_inline("r_t>0")
            + ", 0 for "
            + math_inline("r_t<0")
            + ", removing cases where "
            + math_inline("r_t=0")
            + ". Binary encoding arises naturally in the case of returns series sampled from price bars (i.e., bars that contain prices fluctuating between two symmetric horizontal barriers, centered around the start price), because "
            + math_inline(r"|r_t|")
            + " is approximately constant. When "
            + math_inline(r"|r_t|")
            + " can adopt a wide range of outcomes, binary encoding discards potentially useful information. That is particularly the case when working with intraday time bars, which are affected by the heteroscedasticity that results from the inhomogeneous nature of tick data. One way to partially address this heteroscedasticity is to sample prices according to a subordinated stochastic process. Examples of that are trade bars and volume bars, which contain a fixed number of trades or trades for a fixed amount of volume (see Chapter 2). By operating in this non-chronological, market-driven clock, we sample more frequently during highly active periods, and less frequently during periods of less activity, hence regularizing the distribution of "
            + math_inline(r"|r_t|")
            + " and reducing the need for a large alphabet.</p>"
        )
    if stripped.startswith("Unless price bars are used"):
        return (
            "<p>Unless price bars are used, it is likely that more than two codes will be needed. One approach consists in assigning a code to each "
            + math_inline("r_t")
            + " according to the quantile it belongs to. The quantile boundaries are determined using an in-sample period (training set). There will be the same number of observations assigned to each letter for the overall in-sample, and close to the same number of observations per letter out-of-sample. When using the method, some codes span a greater fraction of "
            + math_inline("r_t")
            + "'s range than others. This uniform (in-sample) or close to uniform (out-of-sample) distribution of codes tends to increase entropy readings on average.</p>"
        )
    if stripped.startswith("One caveat of this method"):
        return (
            "<p>One caveat of this method is that entropy rate is defined in the limit. In the words of Kontoyiannis, “we fix a large integer "
            + math_inline("N")
            + " as the size of our database.” The theorems used by Kontoyiannis' paper prove asymptotic convergence; however, nowhere is a monotonicity property claimed. When a message is short, a solution may be to repeat the same message multiple times.</p>"
            "<p>A second caveat is that, because the window for matching must be symmetric (same length for the dictionary as for the substring being matched), the last bit is only considered for matching if the message's length corresponds to an even number. One solution is to remove the first bit of a message with odd length.</p>"
            "<p>A third caveat is that some final bits will be dismissed when preceded by irregular sequences. This is also a consequence of the symmetric matching window. For example, the entropy rate for “10000111” equals the entropy rate for “10000110,” meaning that the final bit is irrelevant due to the unmatchable “11” in the sixth and seventh bit. When the end of the message is particularly relevant, a good solution may be to analyze the entropy of the reversed message. This not only ensures that the final bits (i.e., the initial ones after the reversing) are used, but actually they will be used to potentially match every bit. Following the previous example, the entropy rate of “11100001” is 0.96, while the entropy rate for “01100001” is 0.84.</p>"
        )
    if stripped.startswith("For the standard Normal"):
        return (
            "<p>For the standard Normal, "
            + math_inline(r"H\approx1.42")
            + ". There are at least two uses of this result. First, it allows us to benchmark the performance of an entropy estimator. We can draw samples from a standard normal distribution, and find what combination of estimator, message length, and encoding gives us an entropy estimate "
            + math_inline(r"\hat H")
            + " sufficiently close to the theoretically derived value "
            + math_inline("H")
            + ". For example, Figure 18.1 plots the bootstrapped distributions of entropy estimates under 10, 7, 5, and 2 letter encodings, on messages of length 100, using Kontoyiannis' method. For alphabets of at least 10 letters, the algorithm in Snippet 18.4 delivers the correct answer. When alphabets are too small, information is discarded and entropy is underestimated. Second, we can use the above equation to connect entropy with volatility, by noting that "
            + math_inline(r"\sigma_H=\frac{e^{H-1/2}}{\sqrt{2\pi}}")
            + ". This gives us an entropy-implied volatility estimate, provided that returns are indeed drawn from a Normal distribution.</p>"
            + chapter_18_figure_18_1_html()
        )
    if stripped.startswith("For q < 0"):
        return "<p>For " + math_inline("q<0") + ", we must require that " + math_inline(r"x_i>0") + ", for all " + math_inline("i") + ". The reason this is a generalized mean is that other means can be obtained as special cases:</p>"
    if stripped.startswith("In the context of information theory"):
        return "<p>In the context of information theory, an interesting special case is " + math_inline(r"x=\{p_i\}_{i=1,\ldots,n}") + ", hence</p>"
    if stripped.startswith("Let us define the quantity Nq"):
        return (
            "<p>Let us define the quantity "
            + math_inline(r"N_q[p]=\frac{1}{M_{q-1}[p,p]}=\left(\sum_{i=1}^{n}p_i^q\right)^{1/(1-q)}")
            + ", for some "
            + math_inline(r"q\ne1")
            + ". Again, for "
            + math_inline(r"q<1")
            + " in "
            + math_inline(r"N_q[p]")
            + ", we must have "
            + math_inline(r"p_i>0")
            + " for all "
            + math_inline("i")
            + ". If "
            + math_inline(r"p_i=1/k")
            + " for "
            + math_inline(r"k\in[1,n]")
            + " different indices and "
            + math_inline(r"p_i=0")
            + " elsewhere, then the weight is spread evenly across "
            + math_inline("k")
            + " different items, and "
            + math_inline(r"N_q[p]=k")
            + " for "
            + math_inline(r"q>1")
            + ". In other words, "
            + math_inline(r"N_q[p]")
            + " gives us the effective number or diversity of items in "
            + math_inline("p")
            + ", according to some weighting scheme set by "
            + math_inline("q")
            + ".</p>"
        )
    if stripped.startswith("Nq [p], we must"):
        return ""
    if stripped.startswith("Using Jensen"):
        return (
            "<p>Using Jensen's inequality, we can prove that</p>"
            + math_display(r"\frac{\partial M_q[p,p]}{\partial q}\ge0,\qquad\frac{\partial N_q[p]}{\partial q}\le0")
        )
    if stripped.startswith("Smaller values"):
        return "<p>Smaller values of " + math_inline("q") + " assign a more uniform weight to elements of the partition, giving relatively more weight to less common elements, and " + math_inline(r"\lim_{q\to0}N_q[p]") + " is simply the total number of nonzero " + math_inline(r"p_i") + ".</p>"
    if stripped.startswith("log[limq"):
        return "<p>This shows that entropy can be interpreted as the logarithm of the effective number of items in a list " + math_inline("p") + ", where " + math_inline(r"q\to1") + ". Figure 18.2 illustrates how the log effective numbers for a family of randomly generated " + math_inline("p") + " arrays converge to Shannon's entropy as " + math_inline("q") + " approaches 1.</p>"
    if stripped.startswith("Shannon’s entropy as q approaches"):
        return "<p>Notice, as well, how their behavior stabilizes as " + math_inline("q") + " grows large. Intuitively, entropy measures information as the level of diversity contained in a random variable. This intuition is formalized through the notion of generalized mean. The implication is that Shannon's entropy is a special case of a diversity measure (hence its connection with volatility). We can now define and compute alternative measures of diversity, other than entropy, where " + math_inline(r"q\ne1") + ".</p>"
    if stripped.startswith("Consider an NxN covariance"):
        return (
            "<p>Consider an "
            + math_inline(r"N\times N")
            + " covariance matrix "
            + math_inline("V")
            + ", computed on returns. First, we compute an eigenvalue decomposition of the matrix, "
            + math_inline(r"VW=W\Lambda")
            + ". Second, we obtain the factor loadings vector as "
            + math_inline(r"f_\omega=W^\prime\omega")
            + ", where "
            + math_inline(r"\omega")
            + " is the vector of allocations, "
            + math_inline(r"\sum_{n=1}^{N}\omega_n=1")
            + ".</p><p class=\"footnote\">1 Alternatively, we could have worked with a vector of holdings, should the covariance matrix had been computed on price changes.</p>"
        )
    if stripped.startswith("loadings vector") or stripped.startswith("1 Alternatively") or stripped.startswith("computed on price changes"):
        return ""
    if stripped.startswith("∑ where N"):
        return "<p>where " + math_inline(r"\sum_{i=1}^{N}\theta_i=1") + ", and " + math_inline(r"\theta_i\in[0,1]") + ", for all " + math_inline(r"i=1,\ldots,N") + ". Fourth, Meucci [2009] proposed the following entropy-inspired definition of portfolio concentration,</p>"
    if stripped.startswith("Easley et al. [1996"):
        return "<p>Easley et al. [1996, 1997] showed that, when the odds of good news / bad news are even, the probability of informed trading (PIN) can be derived as</p>" + math_display(r"PIN=\frac{\alpha\mu}{\alpha\mu+2\varepsilon}")
    if stripped.startswith("At first, this definition"):
        return "<p>At first, this definition of portfolio concentration may sound striking, because " + math_inline(r"\theta_i") + " is not a probability. The connection between this notion of concentration and entropy is due to the generalized mean, which we discussed in Chapter 18, Section 18.7.</p>"
    if stripped.startswith("where μ is the rate") or stripped.startswith("where 𝜇 is the rate"):
        return (
            "<p>where "
            + math_inline(r"\mu")
            + " is the rate of arrival of informed traders, "
            + math_inline(r"\varepsilon")
            + " is the rate of arrival of uninformed traders, and "
            + math_inline(r"\alpha")
            + " is the probability of an informational event. PIN can be interpreted as the fraction of orders that arise from informed traders relative to the overall order flow. Within a volume bar of size "
            + math_inline("V")
            + ", we can classify ticks as buy or sell according to some algorithm, such as the tick rule or the Lee-Ready algorithm. Let "
            + math_inline(r"V_\tau^B")
            + " be the sum of the volumes from buy ticks included in volume bar "
            + math_inline(r"\tau")
            + ", and "
            + math_inline(r"V_\tau^S")
            + " the sum of the volumes from sell ticks within volume bar "
            + math_inline(r"\tau")
            + ". Easley et al. [2012a, 2012b] note that "
            + math_inline(r"\mathbb{E}[|V_\tau^B-V_\tau^S|]\approx\alpha\mu")
            + " and that the expected total volume is "
            + math_inline(r"\mathbb{E}[V_\tau^B+V_\tau^S]=\alpha\mu+2\varepsilon")
            + ". By using a volume clock (Easley et al. [2012c]), we can set the value of "
            + math_inline(r"\mathbb{E}[V_\tau^B+V_\tau^S]=\alpha\mu+2\varepsilon=V")
            + " exogenously. This means that, under a volume clock, PIN reduces to</p>"
        )
    if stripped.startswith("VB where"):
        return "<p>where " + math_inline(r"v_\tau^B=\frac{V_\tau^B}{V}") + ". Note that " + math_inline(r"2v_\tau^B-1") + " represents the order flow imbalance, " + math_inline(r"OI_\tau") + ", which is a bounded real-valued variable, where " + math_inline(r"OI_\tau\in[-1,1]") + ". The VPIN theory thus provides a formal link between the probability of informed trading (PIN) and the persistency of order flow imbalances under a volume clock. See Chapter 19 for further details on this microstructural theory.</p>"
    if stripped.startswith("Persistent order flow imbalance"):
        return (
            "<p>Persistent order flow imbalance is a necessary, non-sufficient condition for adverse selection. For market makers to provide liquidity to informed traders, that order flow imbalance "
            + math_inline(r"|OI_\tau|")
            + " must also have been relatively unpredictable. In other words, market makers are not adversely selected when their prediction of order flow imbalance is accurate, even if "
            + math_inline(r"|OI_\tau|\gg0")
            + ". In order to determine the probability of adverse selection, we must determine how unpredictable the order flow imbalance is. We can determine this by applying information theory.</p>"
            "<p>Consider a long sequence of symbols. When that sequence contains few redundant patterns, it encompasses a level of complexity that makes it hard to describe and predict. Kolmogorov [1965] formulated this connection between redundancy and complexity. In information theory, lossless compression is the task of perfectly describing a sequence with as few bits as possible. The more redundancies a sequence contains, the greater compression rates can be achieved. Entropy characterizes the redundancy of a source, hence its Kolmogorov complexity and its predictability. We can use this connection between the redundancy of a sequence and its unpredictability (by market makers) to derive the probability of adverse selection.</p>"
            "<p>Here we will discuss one particular procedure that derives the probability of adverse selection as a function of the complexity ingrained in the order flow imbalance. First, given a sequence of volume bars indexed by "
            + math_inline(r"\tau=1,\ldots,N")
            + ", each bar of size "
            + math_inline("V")
            + ", we determine the portion of volume classified as buy, "
            + math_inline(r"v_\tau^B\in[0,1]")
            + ". Second, we compute the "
            + math_inline("q")
            + "-quantiles on "
            + math_inline(r"\{v_\tau^B\}")
            + " that define a set "
            + math_inline("K")
            + " of "
            + math_inline("q")
            + " disjoint subsets, "
            + math_inline(r"K=\{K_1,\ldots,K_q\}")
            + ". Third, we produce a mapping from each "
            + math_inline(r"v_\tau^B")
            + " to one of the disjoint subsets, "
            + math_inline(r"f:v_\tau^B\to\{1,\ldots,q\}")
            + ", where "
            + math_inline(r"f[v_\tau^B]=i\Leftrightarrow v_\tau^B\in K_i")
            + " for all "
            + math_inline(r"i\in[1,q]")
            + ". Fourth, we quantize "
            + math_inline(r"\{v_\tau^B\}")
            + " by assigning to each value "
            + math_inline(r"v_\tau^B")
            + " the index of the subset "
            + math_inline("K")
            + " it belongs to, "
            + math_inline(r"f[v_\tau^B]")
            + ". This results in a translation of the set of order imbalances "
            + math_inline(r"\{v_\tau^B\}")
            + " into a quantized message "
            + math_inline(r"X=[f[v_1^B],f[v_2^B],\ldots,f[v_N^B]]")
            + ". Fifth, we estimate the entropy "
            + math_inline(r"H[X]")
            + " using Kontoyiannis' Lempel-Ziv algorithm. Sixth, we derive the cumulative distribution function, "
            + math_inline(r"F[H[X]]")
            + ", and use the time series "
            + math_inline(r"\{F[H[X_\tau]]\}_{\tau=1,\ldots,N}")
            + " as a feature to predict adverse selection.</p>"
        )
    return None


def chapter_20_paragraph_html(text: str) -> str | None:
    stripped = text.strip()
    if stripped in {
        "Task #",
        "Total Amount of Work Amount of Work",
        "Task # Taskgroup #",
        "MULTIPROCESSING",
        "noting that",
        "B",
        "Zb W b=1",
        "r1 =",
        "r2 =",
        "rm =",
    }:
        return ""
    if stripped.startswith(("2 https://pypi", "3 http://scikit-learn", "4 http://stackoverflow", "multiprocessing-pool-ma.")):
        return ""
    if stripped.startswith("A vectorized solution would replace"):
        return (
            "<p>A vectorized solution would replace all explicit iterators (e.g., <code>for ...</code> loops) with matrix algebra operations or compiled iterators or generators. Snippet 20.2 implements the vectorized version of Snippet 20.1. The vectorized version is preferable for four reasons: (1) slow nested <code>for ...</code> loops are replaced with fast iterators; (2) the code infers the dimensionality of the mesh from the dimensionality of <code>dict0</code>; (3) we could run 100 dimensions without having to modify the code, or need 100 <code>for ...</code> loops; and (4) under the hood, Python can run operations in C or C++.</p>"
        )
    if stripped.startswith("Moreover, you could implement"):
        return (
            "<p>Moreover, you could implement the same code to multiprocess a vectorized function, as we did with function <code>applyPtSlOnT1</code> in Chapter 3, where parallel processes execute subroutines that include vectorized pandas objects. In this way, you will achieve two levels of parallelization at once. But why stop there? You could achieve three levels of parallelization at once by running multiprocessed instances of vectorized code in an HPC cluster, where each node in the cluster provides the third level of parallelization. In the next sections, we will explain how multiprocessing works.</p>"
        )
    if stripped.startswith("The simplest way to form molecules"):
        return (
            "<p>The simplest way to form molecules is to partition a list of atoms in subsets of equal size, where the number of subsets is the minimum between the number of processors and the number of atoms. For "
            + math_inline("N")
            + " subsets we need to find the "
            + math_inline("N+1")
            + " indices that enclose the partitions. This logic is demonstrated in Snippet 20.5.</p>"
        )
    if stripped.startswith("Consider two nested loops"):
        return (
            "<p>Consider two nested loops, where the outer loop iterates "
            + math_inline(r"i=1,\ldots,N")
            + " and the inner loop iterates "
            + math_inline(r"j=1,\ldots,i")
            + ". We can order these atomic tasks "
            + math_inline(r"\{(i,j)\mid 1\le j\le i,\ i=1,\ldots,N\}")
            + " as a lower triangular matrix (including the main diagonal). This entails "
            + math_inline(r"\frac{1}{2}N(N-1)+N=\frac{1}{2}N(N+1)")
            + " operations, where "
            + math_inline(r"\frac{1}{2}N(N-1)")
            + " are off-diagonal and "
            + math_inline("N")
            + " are diagonal. We would like to parallelize these tasks by partitioning the atomic tasks into "
            + math_inline("M")
            + " subsets of rows, "
            + math_inline(r"\{S_m\}_{m=1,\ldots,M}")
            + ", each composed of approximately "
            + math_inline(r"\frac{1}{2M}N(N+1)")
            + " tasks. The following algorithm determines the rows that constitute each subset (a molecule).</p>"
        )
    if stripped.startswith("The first subset"):
        return (
            "<p>The first subset, "
            + math_inline("S_1")
            + ", is composed of the first "
            + math_inline("r_1")
            + " rows, that is, "
            + math_inline(r"S_1=\{1,\ldots,r_1\}")
            + ", for a total number of items "
            + math_inline(r"\frac{1}{2}r_1(r_1+1)")
            + ". Then, "
            + math_inline("r_1")
            + " must satisfy the condition</p>"
            + math_display(r"\frac{1}{2}r_1(r_1+1)=\frac{1}{2M}N(N+1)")
            + "<p>Solving for "
            + math_inline("r_1")
            + ", we obtain the positive root</p>"
            + math_display(r"r_1=\frac{-1+\sqrt{1+4N(N+1)M^{-1}}}{2}")
        )
    if stripped.startswith("The second subset contains"):
        return (
            "<p>The second subset contains rows "
            + math_inline(r"S_2=\{r_1+1,\ldots,r_2\}")
            + ", for a total number of items "
            + math_inline(r"\frac{1}{2}(r_2+r_1+1)(r_2-r_1)")
            + ". Then, "
            + math_inline("r_2")
            + " must satisfy the condition</p>"
            + math_display(r"\frac{1}{2}(r_2+r_1+1)(r_2-r_1)=\frac{1}{2M}N(N+1)")
            + "<p>Solving for "
            + math_inline("r_2")
            + ", we obtain the positive root</p>"
            + math_display(r"r_2=\frac{-1+\sqrt{1+4(r_1^2+r_1+N(N+1)M^{-1})}}{2}")
        )
    if stripped.startswith("+ r1 + 1)") or stripped.startswith("(r") or stripped.startswith("N(N + 1). Solving for r2"):
        return ""
    if stripped.startswith("We can repeat the same argument"):
        return (
            "<p>We can repeat the same argument for a future subset "
            + math_inline(r"S_m=\{r_{m-1}+1,\ldots,r_m\}")
            + ", with a total number of items "
            + math_inline(r"\frac{1}{2}(r_m+r_{m-1}+1)(r_m-r_{m-1})")
            + ". Then, "
            + math_inline("r_m")
            + " must satisfy the condition</p>"
            + math_display(r"\frac{1}{2}(r_m+r_{m-1}+1)(r_m-r_{m-1})=\frac{1}{2M}N(N+1)")
            + "<p>Solving for "
            + math_inline("r_m")
            + ", we obtain the positive root</p>"
            + math_display(r"r_m=\frac{-1+\sqrt{1+4(r_{m-1}^2+r_{m-1}+N(N+1)M^{-1})}}{2}")
        )
    if stripped.startswith("N(N + 1). Solving for rm"):
        return ""
    if stripped.startswith("And it is easy to see"):
        return (
            "<p>And it is easy to see that "
            + math_inline("r_m")
            + " reduces to "
            + math_inline("r_1")
            + " where "
            + math_inline(r"r_{m-1}=r_0=0")
            + ". Because row numbers are positive integers, the above results are rounded to the nearest natural number. This may mean that some partitions' sizes may deviate slightly from the "
            + math_inline(r"\frac{1}{2M}N(N+1)")
            + " target. Snippet 20.6 implements this logic.</p>"
        )
    if stripped.startswith("If the outer loop iterates"):
        return (
            "<p>If the outer loop iterates "
            + math_inline(r"i=1,\ldots,N")
            + " and the inner loop iterates "
            + math_inline(r"j=i,\ldots,N")
            + ", we can order these atomic tasks "
            + math_inline(r"\{(i,j)\mid 1\le i\le j,\ j=1,\ldots,N\}")
            + " as an upper triangular matrix (including the main diagonal). In this case, the argument <code>upperTriang=True</code> must be passed to function <code>nestedParts</code>. For the curious reader, this is a special case of the bin packing problem. Figure 20.2 plots a two-nested loops partition of atoms of increasing complexity into molecules. Each of the resulting 6 molecules involves a similar amount of work, even though some atomic tasks are up to 20 times harder than others.</p>"
        )
    if stripped.startswith("In previous chapters we have made frequent use"):
        return "<p>In previous chapters we have made frequent use of <code>mpPandasObj</code>. That function receives six arguments, of which four are optional:</p>"
    if stripped.startswith("Snippet 20.7 lists how mpPandasObj works"):
        return (
            "<p>Snippet 20.7 lists how <code>mpPandasObj</code> works. First, atoms are grouped into molecules, using <code>linParts</code> (equal number of atoms per molecule) or <code>nestedParts</code> (atoms distributed in a lower-triangular structure). When <code>mpBatches</code> is greater than 1, there will be more molecules than cores. Suppose that we divide a task into 10 molecules, where molecule 1 takes twice as long as the rest. If we run this process in 10 cores, 9 of the cores will be idle half of the runtime, waiting for the first core to process molecule 1. Alternatively, we could set <code>mpBatches=10</code> so as to divide that task in 100 molecules. In doing so, every core will receive equal workload, even though the first 10 molecules take as much time as the next 20 molecules. In this example, the run with <code>mpBatches=10</code> will take half of the time consumed by <code>mpBatches=1</code>.</p>"
            "<p>Second, we form a list of jobs. A job is a dictionary containing all the information needed to process a molecule, that is, the callback function, its keyword arguments, and the subset of atoms that form the molecule. Third, we will process the jobs sequentially if <code>numThreads==1</code> (see Snippet 20.8), and in parallel otherwise (see Section 20.5.2). The reason that we want the option to run jobs sequentially is for debugging purposes. It is not easy to catch a bug when programs are run in multiple processors.<sup>1</sup> Once the code is debugged, we will want to use <code>numThreads &gt; 1</code>. Fourth, we stitch together the output from every molecule into a single list, series, or dataframe.</p>"
            '<p class="footnote"><sup>1</sup> Heisenbugs, named after Heisenberg\'s uncertainty principle, describe bugs that change their behavior when scrutinized. Multiprocessing bugs are a prime example.</p>'
        )
    if stripped.startswith("Python has a parallelization library"):
        return (
            "<p>Python has a parallelization library called <code>multiprocessing</code>. This library is the basis for multiprocessing engines such as <code>joblib</code>,<sup>2</sup> which is the engine used by many <code>sklearn</code> algorithms.<sup>3</sup> Snippet 20.9 illustrates how to do an asynchronous call to Python's <code>multiprocessing</code> library. The <code>reportProgress</code> function keeps us informed about the percentage of jobs completed.</p>"
            '<p class="footnote"><sup>2</sup> <a href="https://pypi.python.org/pypi/joblib">https://pypi.python.org/pypi/joblib</a>.</p>'
            '<p class="footnote"><sup>3</sup> <a href="http://scikit-learn.org/stable/developers/performance.html#multi-core-parallelism-using-joblib-parallel">http://scikit-learn.org/stable/developers/performance.html#multi-core-parallelism-using-joblib-parallel</a>.</p>'
        )
    if stripped.startswith("In Snippet 20.9"):
        return (
            "<p>In Snippet 20.9, the instruction <code>pool.imap_unordered()</code> parallelized <code>expandCall</code>, by running each item in <code>jobs</code> (a molecule) in a single thread. Snippet 20.10 lists <code>expandCall</code>, which unwraps the items (atoms) in the job (molecule), and executes the callback function. This little function is the trick at the core of the multiprocessing engine: It transforms a dictionary into a task. Once you understand the role it plays, you will be able to develop your own engines.</p>"
        )
    if stripped.startswith("Multiprocessing must pickle"):
        return (
            "<p>Multiprocessing must pickle methods in order to assign them to different processors. The problem is, bound methods are not pickable.<sup>4</sup> The work around is to add functionality to your engine, that tells the library how to deal with this kind of objects. Snippet 20.11 contains the instructions that should be listed at the top of your multiprocessing engine library. If you are curious about the precise reason this piece of code is needed, you may want to read Ascher et al. [2005], Section 7.5.</p>"
            '<p class="footnote"><sup>4</sup> <a href="http://stackoverflow.com/questions/1816958/cant-pickle-type-instancemethod-when-using-pythons-multiprocessing-pool-ma">http://stackoverflow.com/questions/1816958/cant-pickle-type-instancemethod-when-using-pythons-multiprocessing-pool-ma</a>.</p>'
        )
    if stripped.startswith("What we have presented so far"):
        return (
            "<p>What we have presented so far in this chapter can be used to speed up, by several orders of magnitude, many lengthy and large-scale mathematical operations. In this section we will illustrate an additional motivation for multiprocessing: memory management.</p>"
            "<p>Suppose that you have conducted a spectral decomposition of a covariance matrix of the form "
            + math_inline(r"Z'Z")
            + ", as we did in Chapter 8, Section 8.4.2, where "
            + math_inline("Z")
            + " has size "
            + math_inline(r"T\times N")
            + ". This has resulted in an eigenvectors matrix "
            + math_inline("W")
            + " and an eigenvalues matrix "
            + math_inline(r"\Lambda")
            + ", such that "
            + math_inline(r"Z'ZW=W\Lambda")
            + ". Now you would like to derive the orthogonal principal components that explain a user-defined portion of the total variance, "
            + math_inline(r"0\le\tau\le1")
            + ". In order to do that, we compute "
            + math_inline(r"P=Z\tilde W")
            + ", where "
            + math_inline(r"\tilde W")
            + " contains the first "
            + math_inline(r"M\le N")
            + " columns of "
            + math_inline("W")
            + ", such that</p>"
            + math_display(r"\left(\sum_{m=1}^{M}\Lambda_{m,m}\right)\left(\sum_{n=1}^{N}\Lambda_{n,n}\right)^{-1}\ge\tau")
            + "<p>The computation of "
            + math_inline(r"P=Z\tilde W")
            + " can be parallelized by noting that</p>"
            + math_display(r"P=Z\tilde W=\sum_{b=1}^{B}Z_b\tilde W_b")
            + "<p>where "
            + math_inline(r"Z_b")
            + " is a sparse "
            + math_inline(r"T\times N")
            + " matrix with only "
            + math_inline(r"T\times N_b")
            + " items (the rest are empty), "
            + math_inline(r"\tilde W_b")
            + " is an "
            + math_inline(r"N\times M")
            + " matrix with only "
            + math_inline(r"N_b\times M")
            + " items (the rest are empty), and "
            + math_inline(r"\sum_{b=1}^{B}N_b=N")
            + ". This sparsity is created by dividing the set of columns into a partition of "
            + math_inline("B")
            + " subsets of columns, and loading into "
            + math_inline(r"Z_b")
            + " only the "
            + math_inline("b")
            + "th subset of the columns. This notion of sparsity may sound a bit complicated at first; however, Snippet 20.14 demonstrates how pandas allows us to implement it in a seamless way. Function <code>getPCs</code> receives "
            + math_inline(r"\tilde W")
            + " through the argument <code>eVec</code>. The argument <code>molecules</code> contains a subset of the file names in <code>fileNames</code>, where each file represents "
            + math_inline(r"Z_b")
            + ". The key concept to grasp is that we compute the dot product of a "
            + math_inline(r"Z_b")
            + " with the slice of the rows of "
            + math_inline(r"\tilde W_b")
            + " defined by the columns in "
            + math_inline(r"Z_b")
            + ", and that molecular results are aggregated on the fly (<code>redux=pd.DataFrame.add</code>).</p>"
        )
    if stripped.startswith(("where Zb is a sparse", "NxM matrix with only", "allows us to implement", "the dot product of a Zb", "This sparsity is created")):
        return ""
    if stripped.startswith("This eliminates the need"):
        return "<p>This eliminates the need to process an output list, as <code>mpPandasObj</code> did, hence saving memory and time.</p>"
    if stripped.startswith("This approach presents two advantages"):
        return (
            "<p>This approach presents two advantages: First, because <code>getPCs</code> loads dataframes "
            + math_inline(r"Z_b")
            + " sequentially, for a sufficiently large "
            + math_inline("B")
            + ", the RAM is not exhausted. Second, <code>mpJobList</code> executes the molecules in parallel, hence speeding up the calculations.</p>"
            "<p>In real life ML applications, we often encounter datasets where "
            + math_inline("Z")
            + " contains billions of datapoints. As this example demonstrates, parallelization is not only beneficial in terms of reducing run time. Many problems could not be solved without parallelization, as a matter of memory limitations, even if we were willing to wait longer.</p>"
        )
    return None


def chapter_21_paragraph_html(text: str) -> str | None:
    stripped = text.strip()
    if stripped in {
        "N",
        "i=1",
        "Asset 1 Asset 1 Asset 2 Asset 2 Asset 3 Asset 3",
        "Units of capital Units of capital",
    }:
        return ""
    if stripped.startswith("Consider a set on assets"):
        return (
            "<p>Consider a set of assets "
            + math_inline(r"X=\{x_i\},\ i=1,\ldots,N")
            + ", with returns following a multivariate Normal distribution at each time horizon "
            + math_inline(r"h=1,\ldots,H")
            + ", with varying mean and variance. We will assume that the returns are multivariate Normal, time-independent, however not identically distributed through time. We define a trading trajectory as an "
            + math_inline(r"N\times H")
            + " matrix "
            + math_inline(r"\omega")
            + " that determines the proportion of capital allocated to each of the "
            + math_inline("N")
            + " assets over each of the "
            + math_inline("H")
            + " horizons. At a particular horizon "
            + math_inline(r"h=1,\ldots,H")
            + ", we have a forecasted mean "
            + math_inline(r"\mu_h")
            + ", a forecasted variance "
            + math_inline("V_h")
            + " and a forecasted transaction cost function "
            + math_inline(r"\tau_h[\omega]")
            + ". This means that, given a trading trajectory "
            + math_inline(r"\omega")
            + ", we can compute a vector of expected investment returns "
            + math_inline("r")
            + ", as</p>"
        )
    if stripped.startswith("where 𝜏 [𝜔]"):
        return (
            "<p>where "
            + math_inline(r"\tau[\omega]")
            + " can adopt any functional form. Without loss of generality, consider the following:</p>"
        )
    if stripped.startswith("𝜏 [𝜔] is an Hx1 vector"):
        return (
            "<p>"
            + math_inline(r"\tau[\omega]")
            + " is an "
            + math_inline(r"H\times1")
            + " vector of transaction costs. In words, the transaction costs associated with each asset are the sum of the square roots of the changes in capital allocations, re-scaled by an asset-specific factor "
            + math_inline(r"C_h=\{c_{n,h}\}_{n=1,\ldots,N}")
            + " that changes with "
            + math_inline("h")
            + ". Thus, "
            + math_inline("C_h")
            + " is an "
            + math_inline(r"N\times1")
            + " vector that determines the relative transaction cost across assets.</p>"
        )
    if stripped.startswith("The Sharpe Ratio"):
        return (
            "<p>The Sharpe Ratio (Chapter 14) associated with "
            + math_inline("r")
            + " can be computed as ("
            + math_inline(r"\mu_h")
            + " being net of the risk-free rate)</p>"
        )
    if stripped.startswith("This problem attempts to compute"):
        return (
            "<p>This problem attempts to compute a global dynamic optimum, in contrast to the static optimum derived by mean-variance optimizers (see Chapter 16). Note that non-smooth transaction costs are embedded in "
            + math_inline("r")
            + ". Compared to standard portfolio optimization applications, this is not a convex (quadratic) programming problem for at least three reasons: (1) Returns are not identically distributed, because "
            + math_inline(r"\mu_h")
            + " and "
            + math_inline("V_h")
            + " change with "
            + math_inline("h")
            + ". (2) Transaction costs "
            + math_inline(r"\tau_h[\omega]")
            + " are non-differentiable at zero and changing with "
            + math_inline("h")
            + ". (3) The objective function "
            + math_inline("SR[r]")
            + " is not convex. Next, we will show how to calculate solutions without making use of any analytical property of the objective function (hence the generalized nature of this approach).</p>"
        )
    if stripped.startswith("Suppose that we count"):
        return (
            "<p>Suppose that we count the number of ways that "
            + math_inline("K")
            + " units of capital can be allocated among "
            + math_inline("N")
            + " assets, where we assume "
            + math_inline("K>N")
            + ". This is equivalent to finding the number of non-negative integer solutions to "
            + math_inline(r"x_1+\cdots+x_N=K")
            + ", which has the nice combinatorial solution "
            + math_inline(r"\binom{K+N-1}{N-1}")
            + ". This bears a similarity to the classic integer partitioning problem in number theory for which Hardy and Ramanujan (and later, Rademacher) proved an asymptotic expression (see Johansson [2012]). While order does not matter in the partition problem, order is very relevant to the problem we have at hand.</p>"
        )
    if stripped.startswith("torial solution"):
        return ""
    if stripped.startswith("For example, if K = 6"):
        return (
            "<p>For example, if "
            + math_inline("K=6")
            + " and "
            + math_inline("N=3")
            + ", partitions "
            + math_inline("(1,2,3)")
            + " and "
            + math_inline("(3,2,1)")
            + " must be treated as different (obviously "
            + math_inline("(2,2,2)")
            + " does not need to be permutated). Figure 21.1 illustrates how order is important when allocating 6 units of capital to 3 different assets. This means that we must consider all distinct permutations of each partition. Even though there is a nice combinatorial solution to find the number of such allocations, it may still be computationally intensive to find as "
            + math_inline("K")
            + " and "
            + math_inline("N")
            + " grow large. However, we can use Stirling's approximation to easily arrive at an estimate.</p>"
            "<p>Snippet 21.1 provides an efficient algorithm to generate the set of all partitions,</p>"
        )
    if stripped.startswith("tions, pK,N"):
        return (
            math_display(
                r"p^{K,N}=\left\{\{p_i\}_{i=1,\ldots,N}\mid p_i\in\mathbb{W},\ "
                r"\sum_{i=1}^{N}p_i=K\right\}"
            )
            + "<p>where "
            + math_inline(r"\mathbb{W}")
            + " are the natural numbers including zero (whole numbers).</p>"
        )
    if stripped.startswith("We would like to compute the set of all feasible solutions"):
        return (
            "<p>We would like to compute the set of all feasible solutions at any given horizon "
            + math_inline("h")
            + ", which we denote "
            + math_inline(r"\Omega")
            + ". Consider a partition set of "
            + math_inline("K")
            + " units into "
            + math_inline("N")
            + " assets, "
            + math_inline(r"p^{K,N}")
            + ". For each partition "
            + math_inline(r"\{p_i\}_{i=1,\ldots,N}\in p^{K,N}")
            + ", we can define a vector of absolute weights such that "
            + math_inline(r"|\omega_i|=\frac{1}{K}p_i")
            + ", where "
            + math_inline(r"\sum_{i=1}^{N}|\omega_i|=1")
            + " (the full-investment constraint). This full-investment (without leverage) constraint implies that every weight can be either positive or negative, so for every vector of absolute weights "
            + math_inline(r"\{|\omega_i|\}_{i=1,\ldots,N}")
            + " we can generate "
            + math_inline("2^N")
            + " vectors of (signed) weights. This is accomplished by multiplying the items in "
            + math_inline(r"\{|\omega_i|\}_{i=1,\ldots,N}")
            + " with the items of the Cartesian product of "
            + math_inline(r"\{-1,1\}")
            + " with "
            + math_inline("N")
            + " repetitions. Snippet 21.2 shows how to generate the set "
            + math_inline(r"\Omega")
            + " of all vectors of weights associated with all partitions,</p>"
            + math_display(
                r"\Omega=\left\{\left\{\frac{s_j}{K}p_j\right\}_{j=1,\ldots,N}\ \middle|\ "
                r"\{s_j\}_{j=1,\ldots,N}\in\underbrace{\{-1,1\}\times\cdots\times\{-1,1\}}_{N},\ "
                r"\{p_i\}_{i=1,\ldots,N}\in p^{K,N}\right\}."
            )
        )
    if stripped.startswith(("lute weights", "K i | j", "⏟")):
        return ""
    if stripped.startswith("Given the set of all vectors Ω"):
        return (
            "<p>Given the set of all vectors "
            + math_inline(r"\Omega")
            + ", we define the set of all possible trajectories "
            + math_inline(r"\Phi=\underbrace{\Omega\times\cdots\times\Omega}_{H}")
            + " as the Cartesian product of "
            + math_inline(r"\Omega")
            + " with "
            + math_inline("H")
            + " repetitions. Then, for every trajectory we can evaluate its transaction costs and "
            + math_inline("SR")
            + ", and select the trajectory with optimal performance across "
            + math_inline(r"\Phi")
            + ". Snippet 21.3 implements this functionality. The object <code>params</code> is a list of dictionaries that contain the values of "
            + math_inline("C")
            + ", "
            + math_inline(r"\mu")
            + ", "
            + math_inline("V")
            + ".</p>"
        )
    if stripped.startswith("Snippet 21.5 generates"):
        return (
            "<p>Snippet 21.5 generates "
            + math_inline("H")
            + " vectors of means, covariance matrices, and transaction cost factors, "
            + math_inline("C")
            + ", "
            + math_inline(r"\mu")
            + ", "
            + math_inline("V")
            + ". These variables are stored in a <code>params</code> list.</p>"
        )
    if stripped.startswith("Note that this procedure selects"):
        return (
            "<p>Note that this procedure selects a globally optimal trajectory without relying on convex optimization. A solution will be found even if the covariance matrices are ill-conditioned, transaction cost functions are non-smooth, etc. The price we pay for this generality is that calculating the solution is extremely computationally intensive. Indeed, evaluating all trajectories is similar to the traveling-salesman problem.</p>"
        )
    return None


def chapter_22_paragraph_html(text: str) -> str | None:
    stripped = text.strip()
    figure_text_fragments = (
        "QDR Infiniband",
        "Compute Servers 504 Nodes",
        "QDR InfiniBand Aggregation Switch",
        "Big Memory ANI Servers",
        "GPU Servers 266 Nvidia",
        "IB 10G - TCPoEth",
        "Performance",
        "90 T T+1",
        "Electricity Usage (KWh)",
        "Temperature (°F)",
        "Hour (",
        "90 LTAP(T)",
        "GTB(T)",
        "M(T+1)",
        "not able to predict the baseline",
        "+ + 70",
        "+ + + +",
        "+ + M(T)",
    )
    caption_continuations = {
        "2010)",
        "much more significant (circa 2010)",
        "result of the extensive automation in classification of astronomical observations",
        "minutes during the market hours",
        "21 times longer when the same data is in ASCII files (603.98 seconds versus approximately 3.5 hours)",
        "according to their average.",
        "FFT identifies strong presence of activities happening once per day (frequency = 366), twice per day (frequency = 732), and once per minute (frequency = 527040 = 366*24*60).",
    }
    if stripped in caption_continuations or stripped.startswith(figure_text_fragments):
        return ""
    if stripped.startswith("High-Performance Computational Intelligence and Forecasting Technologies"):
        return '<p class="chapter-authors">Kesheng Wu and Horst D. Simon</p>'
    if stripped.startswith("agencies to come up with an investigation report"):
        return (
            "<p>agencies to come up with an investigation report. In front of a congressional panel investigating the crash, the data volume (~20 terabytes) was given as the primary reason for the long delay. Since HPC systems, such as those at National Energy Research Scientific Computing (NERSC) center,<sup>1</sup> routinely work with hundreds of terabytes in minutes, we should have no problem processing the data from financial markets. This led to the establishment of the CIFT project with the mission to apply the HPC techniques and tools for financial data analysis. A key aspect of financial big data is that it consists of mostly time series. Over the years, the CIFT team, along with numerous collaborators, has developed techniques to analyze many different forms of data streams and time series. This chapter provides a brief introduction to the HPC system including both hardware (Section 22.4) and software (Section 22.5), and recounts a few successful use cases (Section 22.6). We conclude with a summary of our vision and work so far and also provide contact information for interested readers.</p>"
            '<p class="footnote"><sup>1</sup> NERSC is a National User Facility funded by U.S. Department of Energy, located at LBNL. More information about NERSC can be found at <a href="http://nersc.gov/">http://nersc.gov/</a>.</p>'
        )
    if stripped.startswith(("1 NERSC is", "mation about NERSC")):
        return ""
    if stripped.startswith("Legend has it that the first generation"):
        paragraph = (
            "Legend has it that the first generation of big data systems was built with the spare computer components gleaned from a university campus. "
            "This is likely an urban legend, but it underscores an important point about the difference between HPC systems and cloud systems. "
            "Theoretically, an HPC system is built with custom high-cost components, while cloud systems are built with standard low-cost commodity components. "
            "In practice, since the worldwide investment in HPC systems is much smaller than that of personal computers, there is no way for manufacturers to produce custom components just for the HPC market. "
            "The truth is that HPC systems are largely assembled from commodity components just like cloud systems. "
            "However, due to their different target applications, there are some differences in their choices of the components. "
            "Let us describe the computing elements, storage system, and networking system in turn. "
            "Figure 22.1 is a high-level schematic diagram representing the key components of the Magellan cluster around year 2010 (Jackson et al. [2010]; Yelick et al. [2011]). "
            "The computer elements include both CPUs and graphics processing units (GPUs). These CPUs and GPUs are commercial products in almost all the cases. "
            "For example, the nodes on dirac1 use a 24-core 2.2GHz Intel processor, which is common to cloud computing systems. Currently, dirac1 does not contain GPUs. "
            "The networking system consists of two parts: the InfiniBand network connecting the components within the cluster, and the switched network connection to the outside world. "
            "In this particular example, the outside connections are labeled “ESNet” and “ANI.” The InfiniBand network switches are also common in cloud computing systems. "
            "The storage system in Figure 22.1 includes both rotating disks and flash storage. This combination is also common. "
            "What is different is that an HPC system typically has its storage system concentrated outside of the computer nodes, while a typical cloud computing system has its storage system distributed among the compute nodes. "
            "These two approaches have their own advantages and disadvantages. For example, the concentrated storage is typically exported as a global file system to all computer nodes, which makes it easier to deal with data stored in files. "
            "However, this requires a highly capable network connecting the CPUs and the disks."
        )
        return f"<p>{mathify_general_text(paragraph)}</p>"
    if stripped.startswith("high-cost components"):
        return ""
    if stripped.startswith("the distributed approach"):
        return (
            "<p>"
            + mathify_general_text(
                "In contrast, the distributed approach could use lower-capacity network because there is some storage that is close to each CPU. "
                "Typically, a distributed file system, such as the Google file system (Ghemawat, Gobioff, and Leung [2003]), is layered on top of a cloud computing system to make the storage accessible to all CPUs. "
                "In short, the current generation of HPC systems and cloud systems use pretty much the same commercial hardware components. Their differences are primarily in the arrangement of the storage systems and networking systems. "
                "Clearly, the difference in the storage system designs could affect the application performance. However, the virtualization layer of the cloud systems is likely the bigger cause of application performance difference. "
                "In the next section, we will discuss another factor that could have an even larger impact, namely software tools and libraries."
            )
            + "</p><p>"
            + mathify_general_text(
                "Virtualization is generally used in the cloud computing environment to make the same hardware available to multiple users and to insulate one software environment from another. "
                "This is one of the more prominent features distinguishing the cloud computing environment from the HPC environment. "
                "In most cases, all three basic components of a computer system—CPU, storage, and networking—are all virtualized. "
                "This virtualization has many benefits. For example, an existing application can run on a CPU chip without recompiling; many users can share the same hardware; hardware faults could be corrected through the virtualization software; and applications on a failed compute node could be more easily migrated to another node. "
                "However, this virtualization layer also imposes some runtime overhead and could reduce application performance. For time-sensitive applications, this reduction in performance could become a critical issue."
            )
            + "</p><p>"
            + mathify_general_text(
                "Tests show that the performance differences could be quite large. Next, we briefly describe a performance study reported by Jackson et al. [2010]. "
                "Figure 22.2 shows the performance slowdown using different computer systems. The names below the horizontal axis are different software packages commonly used at NERSC. "
                "The left bar corresponds to the Commercial Cloud, the middle bar to Magellan, and the right bar, when present, to the EC2-Beta-Opt system. "
                "The non-optimized commercial cloud instances run these software packages 2 to 10 times slower than on a NERSC supercomputer. Even on the more expensive high-performance instances, there are noticeable slowdowns."
            )
            + "</p>"
            + chapter_22_figure_html("22.2")
            + "<p>"
            + mathify_general_text(
                "Figure 22.3 shows a study of the main factor causing the slowdown with the software package PARATEC. "
                "In Figure 22.2, we see that PARATEC took 53 times longer to complete on the commercial cloud than on an HPC system. "
                "We observe from Figure 22.3 that, as the number of cores (horizontal axis) increases, the differences among the measured performances (measured in TFLOP/s) become larger. "
                "In particular, the line labeled “10G-TCPoEth Vm” barely increases as the number of cores grows. This is the case where the network instance is using virtualized networking (TCP over Ethernet). "
                "It clearly shows that the networking virtualization overhead is significant, to the point of rendering the cloud useless."
            )
            + "</p>"
            + chapter_22_figure_html("22.3")
            + "<p>"
            + mathify_general_text(
                "The issue of virtualization overhead is widely recognized (Chen et al. [2015]). There has been considerable research aimed at addressing both the I/O virtualization overhead (Gordon et al. [2012]) as well as the networking virtualization overhead (Dong et al. [2012]). "
                "As these state-of-the-art techniques are gradually being moved into commercial products, we anticipate the overhead will decrease in the future, but some overhead will inevitably remain. "
                "To wrap up this section, we briefly touch on the economics of HPC versus cloud. Typically, HPC systems are run by nonprofit research organizations and universities, while cloud systems are provided by commercial companies. "
                "Profit, customer retention, and many other factors affect the cost of a cloud system (Armbrust et al. [2010]). "
                "In 2011, the Magellan project report stated that “Cost analysis shows that DOE centers are cost competitive, typically 3–7 × less expensive, when compared to commercial cloud providers” (Yelick et al. [2011]). "
                "A group of high-energy physicists thought their use case was well-suited for cloud computing and conducted a detailed comparison study (Holzman et al. [2017]). "
                "Their cost comparisons still show the commercial cloud offerings as approximately 50% more expensive than dedicated HPC systems for comparable computing tasks; however, the authors worked with severe limitations on data ingress and egress to avoid potentially hefty charges on data movement. "
                "For complex workloads, such as the streaming data analyses discussed in this book, we anticipate that this HPC cost advantage will remain in the future. "
                "A 2016 National Academy of Sciences study came to the same conclusion that even a long-term lease from Amazon is likely 2 to 3 times more expensive than HPC systems to handle the expected science workload from NSF (Box 6.2 from National Academies of Sciences [2016])."
            )
            + "</p>"
        )
    if stripped.startswith(("cloud instances run these software", "approximately 50% more expensive")):
        return ""
    if stripped.startswith("In short, we believe the HPC community"):
        return (
            "<p>In short, we believe the HPC community has a lot to offer to advance the state-of-the-art for streaming analytics. The CIFT project was established with a mission to transfer LBNL's HPC expertise to streaming business applications. We are pursuing this mission via collaboration, demonstration, and tool development. To evaluate the potential uses of HPC technology, we have spent time working with various applications. This process not only exposes our HPC experts to a variety of fields, but also makes it possible for us to gather financial support to establish a demonstration facility. With the generous gifts from a number of early supporters of this effort, we established a substantial computing cluster dedicated to this work. This dedicated computer (named dirac1) allows users to utilize an HPC system and evaluate their applications for themselves. We are also engaged in a tool development effort to make HPC systems more usable for streaming data analysis. In the following sections, we will describe the hardware and software of the dedicated CIFT machine, as well as some of the demonstration and tool development efforts. Highlights include improving the data handling speed by 21-fold, and increasing the speed of computing an early warning indicator by 720-fold.</p>"
        )
    if stripped.startswith("In describing the HPC hardware components"):
        return (
            "<p>In describing the HPC hardware components, we noted that the storage systems in an HPC platform are typically different from those in a cloud platform. Correspondingly, the software libraries used by most users for accessing the storage systems are different as well. This difference can be traced to the difference in the conceptual models of data. Typically, HPC applications treat data as multi-dimensional arrays and, therefore, the most popular I/O libraries on HPC systems are designed to work with multi-dimensional arrays. Here, we describe the most widely used array format library, HDF5 (Folk et al. [2011]). HDF5 is the fifth iteration of the Hierarchical Data Format, produced by the HDF Group.<sup>2</sup> The basic unit of data in HDF5 is an array plus its associated information such as attributes, dimensions, and data type. Together, they are known as a data set. Data sets can be grouped into large units called groups, and groups can be organized into high-level groups. This flexible hierarchical organization allows users to express complex relationships among the data sets. Beyond the basic library for organizing user data into files, the HDF Group also provides a suite of tools and specialization of HDF5 for different applications. For example, HDF5 includes a performance profiling tool. NASA has a specialization of HDF5, named HDF5-EOS, for data from their Earth-Observing System (EOS); and the next-generation DNA sequence community has produced a specialization named BioHDF for their bioinformatics data. HDF5 provides an efficient way for accessing the storage systems on HPC platform. In tests, we have demonstrated that using HDF5 to store stock markets data significantly speeds up the analysis operations. This is largely due to its efficient compression/decompression algorithms that minimize network traffic and I/O operations, which brings us to our next point.</p>"
            '<p class="footnote"><sup>2</sup> The HDF Group web site is <a href="https://www.hdfgroup.org/">https://www.hdfgroup.org/</a>.</p>'
        )
    if stripped.startswith("2 The HDF Group"):
        return ""
    if stripped.startswith("To address the above issue"):
        return (
            "<p>To address the above issue, we devised a number of white-box approaches, the most effective of which, known as LTAP, is reported here. LTAP is based on the fact that the aggregate variable electricity usage per day is accurately described by a piecewise linear function of average daily temperature. This fact allows us to make predictions about the total daily electricity usage. By further assuming that the usage profile of each household remains the same during the study, we are able to assign the hourly usage values from the daily aggregate usage. This approach is shown to be self-consistent; that is, the prediction procedure exactly reproduces the electricity usage in year T-1, and the predictions for the control group in both year T and T + 1 are very close to the actual measured values. Both treatment groups have reduced electricity usages during the peak-demand hours, and the active group reduced the usage more than the passive group. This observation is in line with other studies.</p>"
            "<p>Though the new data-driven baseline model LTAP predicts the average usages of the control group accurately, there are some differences in predicted impact of the new time-of-use pricing intended to reduce the usage during the peak-demand hours (see Figure 22.6). For example, with the control group as the baseline, the active group reduces its usage by 0.277 kWh (out of about 2 kWh) averaged over the peak-demand hours in the first year with the new price and 0.198 kWh in the second year. Using LTAP as the baseline, the average reductions are only 0.164 kWh for both years. Part of the difference may be due to the self-selection bias in treatment groups, especially the active group, where the households have to explicitly opt-in to participate in the trial. It is likely that the households that elected to join the active group are well-suited to take advantage of the proposed new pricing structure. We believe that the LTAP baseline is a way to address the self-selection bias and plan to conduct additional studies to further verify this.</p>"
            + chapter_22_figure_22_6_html()
        )
    if stripped.startswith("Though this work concentrates on demonstrating"):
        return (
            "<p>Though this work concentrates on demonstrating that the new baseline models are effective for groups, we believe that these new models are also useful for studying individual households in the future. We explored a number of standard black-box approaches. Among machine learning methods, we found gradient tree boosting (GTB) to be more effective than others. However, the most accurate GTB models require lagged variables as features (for example, the electricity usage a day before and a week before). In our work, we need to use the data from year T-1 to establish the baseline usage for year T and year T + 1. The lagged variable for a day before and a week before would be incorporating recent information not in year T-1. We attempted to modify the prediction procedure to use the recent predictions in place of the actual measured values a day before and a week before; however, our tests show that the prediction errors accumulate over time, leading to unrealistic predictions a month or so into the summer season. This type of accumulation of prediction errors is common to continuous prediction procedures for time series.</p>"
            "<p>To address the above issue, we devised a number of white-box approaches, the most effective of which, known as LTAP, is reported here. LTAP is based on the fact that the aggregate variable electricity usage per day is accurately described by a piecewise linear function of average daily temperature. This fact allows us to make predictions about the total daily electricity usage. By further assuming that the usage profile of each household remains the same during the study, we are able to assign the hourly usage values from the daily aggregate usage. This approach is shown to be self-consistent; that is, the prediction procedure exactly reproduces the electricity usage in year T-1, and the predictions for the control group in both year T and T + 1 are very close to the actual measured values. Both treatment groups have reduced electricity usages during the peak-demand hours, and the active group reduced the usage more than the passive group. This observation is in line with other studies.</p>"
            "<p>Though the new data-driven baseline model LTAP predicts the average usages of the control group accurately, there are some differences in predicted impact of the new time-of-use pricing intended to reduce the usage during the peak-demand hours (see Figure 22.6). For example, with the control group as the baseline, the active group reduces its usage by 0.277 kWh (out of about 2 kWh) averaged over the peak-demand hours in the first year with the new price and 0.198 kWh in the second year. Using LTAP as the baseline, the average reductions are only 0.164 kWh for both years. Part of the difference may be due to the self-selection bias in treatment groups, especially the active group, where the households have to explicitly opt-in to participate in the trial. It is likely that the households that elected to join the active group are well-suited to take advantage of the proposed new pricing structure. We believe that the LTAP baseline is a way to address the self-selection bias and plan to conduct additional studies to further verify this.</p>"
            + chapter_22_figure_22_6_html()
        )
    if stripped.startswith("Though the new data-driven baseline model"):
        return ""
    if stripped.startswith("sift through tens of terabytes"):
        return (
            "<p>The extended time it took for the SEC and CFTC to investigate the Flash Crash of 2010 was the original motivation for CIFT's work. Federal investigators needed to sift through tens of terabytes of data to look for the root cause of the crash. Since CFTC publicly blamed the volume of data to be the source of the long delay, we started our work by looking for HPC tools that could easily handle tens of terabytes. Since HDF5 is the most commonly used I/O library, we started our work by applying HDF5 to organize a large set of stock trading data (Bethel et al. [2011]).</p>"
        )
    if stripped.startswith("The extended time it took for the SEC"):
        return ""
    if stripped.startswith("Let us quickly review"):
        return (
            "<p>"
            + mathify_general_text(
                "Let us quickly review what happened during the 2010 Flash Crash. On May 6, at about 2:45 p.m. (U.S. Eastern Daylight Time), the Dow Jones Industrial Average dropped almost 10%, and many stocks traded at one cent per share, the minimum price for any possible trade. "
                "Figure 22.7 shows an example of another extreme case, where shares of Apple (symbol AAPL) traded at $100,000 per share, the maximum possible price allowed by the exchange. Clearly, these were unusual events, which undermined investors’ faith and confidence in our financial markets."
            )
            + "</p>"
            + chapter_22_figure_html("22.7")
            + "<p>"
            + mathify_general_text(
                "Investors demanded to know what caused these events. To make our work relevant to the financial industry, we sought to experiment with the HDF5 software, and apply it to the concrete task of computing early-warning indicators. "
                "Based on recommendations from a group of institutional investors, regulators, and academics, we implemented two sets of indicators that have been shown to have “early warning” properties preceding the Flash Crash. "
                "They are the Volume Synchronized Probability of Informed Trading (VPIN) (Easley, Lopez de Prado, and O’Hara [2011]) and a variant of the Herfindahl-Hirschman Index (HHI) (Hirschman [1980]) of market fragmentation. "
                "We implemented these two algorithms in the C++ language, while using MPI for inter-processor communication, to take full advantage of the HPC systems. "
                "The reasoning behind this choice is that if any of these early-warning indicators is shown to be successful, the high-performance implementation would allow us to extract the warning signals as early as possible so there might be time to take corrective actions."
            )
            + "</p><p>"
            + mathify_general_text(
                "Our effort was one of the first steps to demonstrate that it is possible to compute the early-warning signals fast enough. "
                "For our work, we implemented two versions of the programs: one uses data organized in HDF5 files, and another reads the data from the commonly used ASCII text files. "
                "Figure 22.8 shows the time required to process the trading records of all S&P 500 stocks over a 10-year timespan. "
                "Since the size of the 10-year trading data is still relatively small, we replicated the data 10 times as well. "
                "On a single CPU core (labeled “Serial” in Figure 22.8), it took about 3.5 hours with ASCII data, but only 603.98 seconds with HDF5 files. "
                "When 512 CPU cores are used, this time reduces to 2.58 seconds using HDF5 files, resulting in a speedup of 234 times. "
                "On the larger replicated dataset, the advantage of HPC code for computing these indices is even more pronounced. With 10 times as much data, it took only about 2.3 times longer for the computer to complete the tasks, a below-linear latency increase."
            )
            + "</p>"
            + chapter_22_figure_html("22.8")
            + "<p>"
            + mathify_general_text(
                "Using more CPU makes HPC even more scalable. Figure 22.8 also shows that with a large data set, we can further take advantage of the indexing techniques available in HDF5 to reduce the data access time, which in turn reduces the overall computation time. "
                "When 512 CPU cores are used, the total runtime is reduced from 16.95 seconds to 4.59 seconds, a speedup of 3.7 due to this HPC technique of indexing."
            )
            + "</p>"
        )
    if stripped.startswith(("possible price allowed", "times longer for the computer")):
        return ""
    if stripped.startswith("With a faster program to compute VPIN"):
        return (
            "<p>With a faster program to compute VPIN, we were also able to explore the parametric choices more closely. For example, we were able to identify the parameter values that reduce VPIN's false positive rate over one hundred contracts from 20% to only 7%, see Figure 22.9. The parameter choices to achieve this performance are: (1) pricing the volume bar with the median prices of the trades (not the closing price typically used in analyses), (2) 200 buckets per day, (3) 30 bars per bucket, (4) support window for computing VPIN = 1 day, event duration = 0.1 day, (5) bulk volume classification with Student t-distribution with "
            + math_inline(r"\nu=0.1")
            + ", and (6) threshold for CDF of VPIN = 0.99. Again, these parameters provide a low false positive rate on the totality of futures contracts, and are not the result of individual fitting. On different classes of futures contracts, it is possible to choose different parameters to achieve even lower false positive rates. In some cases, the false positive rates can fall significantly below 1%. Based on Figure 22.9, interest rate and index futures contracts typically have lower false positive rates. The futures contracts on commodities, such as energy and metal, generally have higher false positive rates. Additionally, a faster program for computing VPIN allows us to validate that the events identified by VPIN are “intrinsic,” in the sense that varying parameters such as the threshold on VPIN CDF only slightly change the number of events detected. Had the events been random, changing this threshold from 0.9 to 0.99 would have reduced the number of events by a factor of 10. In short, a faster VPIN program also allows us to confirm the real-time effectiveness of VPIN.</p>"
        )
    if stripped.startswith("Fourier Transform High Frequency Trading is pervasive"):
        return ""
    if stripped.startswith("brought together a number of high performance"):
        return (
            "<p>"
            + mathify_general_text(
                "High Frequency Trading is pervasive across all electronic financial markets. As algorithms replace tasks previously performed by humans, cascading effects similar to the 2010 Flash Crash may become more likely. "
                "In our work (Song et al. [2014]), we brought together a number of high-performance signal-processing tools to improve our understanding of these trading activities. "
                "As an illustration, we summarize the Fourier analysis of the trading prices of natural gas futures. Normally, Fourier analysis is applied on uniformly spaced data. "
                "Since market activity comes in bursts, we may want to sample financial time series according to an index of trading activity. For example, VPIN samples financial series as a function of volume traded. "
                "However, a Fourier analysis of financial series in chronological time may still be instructive. To this purpose, we use a non-uniform Fast Fourier Transform (FFT) procedure."
            )
            + "</p><p>"
            + mathify_general_text(
                "From the Fourier analysis of the natural gas futures market, we see strong evidence of High Frequency Trading in the market. "
                "The Fourier components corresponding to high frequencies are (1) becoming more prominent in recent years and (2) much stronger than could be expected from the structure of the market. "
                "Additionally, a significant amount of trading activity occurs in the first second of every minute, which is a tell-tale sign of trading triggered by algorithms that target a Time-Weighted Average Price (TWAP). "
                "Fourier analysis on trading data shows that activities at the once-per-minute frequency are considerably higher than at neighboring frequencies (see Figure 22.10). "
                "Note that the vertical axis is in logarithmic scale. The strength of activities at once-per-minute frequency is more than ten times stronger than the neighboring frequencies. "
                "Additionally, the activity is very precisely defined at once-per-minute, which indicates that these trades are triggered by intentionally constructed automated events. We take this to be strong evidence that TWAP algorithms have a significant presence in this market."
            )
            + "</p><p>"
            + mathify_general_text(
                "We expected the frequency analysis to show strong daily cycles. In Figure 22.10, we expect amplitude for frequency 365 to be large. "
                "However, we see the highest amplitude was for the frequency of 366. This can be explained because 2012 was a leap year. "
                "This is a validation that the non-uniform FFT is capturing the expected signals. The second- and third-highest amplitudes have the frequencies of 732 and 52, which are twice-a-day and once-a-week. "
                "These are also unsurprising. We additionally applied the non-uniform FFT on the trading volumes and found further evidence of algorithmic trading. "
                "Moreover, the signals pointed to a stronger presence of algorithmic trading in recent years. Clearly, the non-uniform FFT algorithm is useful for analyzing highly irregular time series."
            )
            + "</p>"
            + chapter_22_figure_html("22.10")
        )
    if stripped.startswith("amplitude was for the frequency"):
        return ""
    if stripped.startswith("Currently, there are two primary ways"):
        return (
            "<p>Currently, there are two primary ways to construct large-scale computing platforms: the HPC approach and the cloud approach. Most of the scientific computing efforts use the HPC approach, while most of the business computing needs are satisfied through the cloud approach. The conventional wisdom is that the HPC approach occupies a small niche of little consequence. This is not true. HPC systems are essential to the progress of scientific research. They played important roles in exciting new scientific discoveries including the Higgs particle and gravitational waves. They have spurred the development of new subjects of study, such as behavioral economics, and new ways of conducting commerce through the Internet. The usefulness of extremely large HPC systems has led to the 2015 National Strategic Computing Initiative.<sup>3</sup> There are efforts to make HPC tools even more useful by accelerating their adoption in business applications. The HPC4Manufacturing<sup>4</sup> effort is pioneering this knowledge transfer to the U.S. manufacturing industry, and has attracted considerable attention. Now is the time to make a more concerted push for HPC to meet other critical business needs. In recent years, we have developed CIFT as a broad class of business applications that could benefit from the HPC tools and techniques. In decisions such as how to respond to a voltage fluctuation in a power transformer and an early warning signal of impending market volatility event, HPC software tools could help determine the signals early enough for decision makers, provide sufficient confidence about the prediction, and anticipate the consequence before the catastrophic event arrives. These applications have complex computational requirements and often have a stringent demand on response time as well. HPC tools are better suited to meet these requirements than cloud-based tools. In our work, we have demonstrated that the HPC I/O library HDF5 can be used to accelerate the data access speed by 21-fold, and HPC techniques can accelerate the computation of the Flash Crash early-warning indicator VPIN by 720-fold. We have developed additional algorithms that enable us to predict the daily peak electricity usage years into the future.</p>"
            '<p class="footnote"><sup>3</sup> The National Strategic Computing Initiative plan is available online at <a href="https://www.whitehouse.gov/sites/whitehouse.gov/files/images/NSCI%20Strategic%20Plan.pdf">https://www.whitehouse.gov/sites/whitehouse.gov/files/images/NSCI%20Strategic%20Plan.pdf</a>. The Wikipedia page on this topic (<a href="https://en.wikipedia.org/wiki/National_Strategic_Computing_Initiative">https://en.wikipedia.org/wiki/National_Strategic_Computing_Initiative</a>) also has some useful links to additional information.</p>'
            '<p class="footnote"><sup>4</sup> Information about HPC4Manufacturing is available online at <a href="https://hpc4mfg.llnl.gov/">https://hpc4mfg.llnl.gov/</a>.</p>'
        )
    if stripped.startswith("usage years into the future"):
        return (
            '<p>We anticipate that applying HPC tools and techniques to other applications could achieve similarly significant results. In addition to the performance advantages mentioned above, a number of published studies (Yelick et al. [2011], Holzman et al. [2017]) show HPC systems to have a significant price advantage as well. Depending on the workload’s requirement on CPU, storage, and networking, using a cloud system might cost 50% more than using an HPC system, and, in some cases, as much as seven times more. For the complex analytical tasks described in this book, with their constant need to ingest data for analysis, we anticipate the cost advantage will continue to be large. CIFT is expanding the effort to transfer HPC technology to private companies, so that they can also benefit from the price and performance advantages enjoyed by large-scale research facilities. Our earlier collaborators have provided the funds to start a dedicated HPC system for our work. This resource should make it considerably easier for interested parties to try out their applications on an HPC system. We are open to different forms of collaborations. For further information regarding CIFT, please visit CIFT’s web page at <a href="http://crd.lbl.gov/cift/">http://crd.lbl.gov/cift/</a>.</p>'
        )
    if stripped.startswith(("3 The National Strategic", "sites/whitehouse.gov/files/images")):
        return ""
    if stripped.startswith("The CIFT project is the brainchild"):
        return "<p>The CIFT project is the brainchild of Dr. David Leinweber. Dr. Horst Simon brought it to LBNL in 2010. Drs. E. W. Bethel and D. Bailey led the project for four years. The CIFT project has received generous gifts from a number of donors. This work is supported in part by the Office of Advanced Scientific Computing Research, Office of Science, of the U.S. Department of Energy under Contract No. DE-AC02-05CH11231. This research also uses resources of the National Energy Research Scientific Computing Center supported under the same contract.</p>"
    replacements = {
        "state-ofthe-art": "state-of-the-art",
        "pointto-point": "point-to-point",
        "inflight analysis": "in-flight analysis",
        "cuttingedge": "cutting-edge",
        "onceper-minute": "once-per-minute",
        "DE-AC02- 05CH11231": "DE-AC02-05CH11231",
        "a HPC": "an HPC",
        "Figure 1 includes": "Figure 22.1 includes",
        "In Figure 2,": "In Figure 22.2,",
        "Figure 3 that": "Figure 22.3 that",
        "from Figure 3": "from Figure 22.3",
        "strong evidences": "strong evidence",
        "high performance signal-processing": "high-performance signal-processing",
    }
    cleaned = stripped
    for old, new in replacements.items():
        cleaned = cleaned.replace(old, new)
    if cleaned != stripped:
        return f"<p>{mathify_general_text(cleaned)}</p>"
    return None


def chapter_paragraph_html(chapter: Chapter, text: str) -> str | None:
    marker = text.strip().upper()
    reference_markers = {
        "REFERENCES": "References",
        "REFERENCE": "Reference",
        "BIBLIOGRAPHY": "Bibliography",
    }
    if marker in reference_markers:
        section_id = slugify(reference_markers[marker])
        return f'<h2 class="references-heading" id="{section_id}">{reference_markers[marker]}</h2>'
    if chapter.slug == "chapter-01":
        override = chapter_01_paragraph_html(text)
        if override is not None:
            return override
    if chapter.slug == "chapter-03":
        override = chapter_03_paragraph_html(text)
        if override is not None:
            return override
    if chapter.slug == "chapter-04":
        override = chapter_04_paragraph_html(text)
        if override is not None:
            return override
    if chapter.slug == "chapter-05":
        override = chapter_05_paragraph_html(text)
        if override is not None:
            return override
    if chapter.slug == "chapter-06":
        override = chapter_06_paragraph_html(text)
        if override is not None:
            return override
    if chapter.slug == "chapter-07":
        override = chapter_07_paragraph_html(text)
        if override is not None:
            return override
    if chapter.slug == "chapter-08":
        override = chapter_08_paragraph_html(text)
        if override is not None:
            return override
    if chapter.slug == "chapter-09":
        override = chapter_09_paragraph_html(text)
        if override is not None:
            return override
    if chapter.slug == "chapter-10":
        override = chapter_10_paragraph_html(text)
        if override is not None:
            return override
    if chapter.slug == "chapter-11":
        override = chapter_11_paragraph_html(text)
        if override is not None:
            return override
    if chapter.slug == "chapter-12":
        override = chapter_12_paragraph_html(text)
        if override is not None:
            return override
    if chapter.slug == "chapter-13":
        override = chapter_13_paragraph_html(text)
        if override is not None:
            return override
    if chapter.slug == "chapter-14":
        override = chapter_14_paragraph_html(text)
        if override is not None:
            return override
    if chapter.slug == "chapter-16":
        override = chapter_16_paragraph_html(text)
        if override is not None:
            return override
    if chapter.slug == "chapter-17":
        override = chapter_17_paragraph_html(text)
        if override is not None:
            return override
    if chapter.slug == "chapter-18":
        override = chapter_18_paragraph_html(text)
        if override is not None:
            return override
    if chapter.slug == "chapter-20":
        override = chapter_20_paragraph_html(text)
        if override is not None:
            return override
    if chapter.slug == "chapter-21":
        override = chapter_21_paragraph_html(text)
        if override is not None:
            return override
    if chapter.slug == "chapter-22":
        override = chapter_22_paragraph_html(text)
        if override is not None:
            return override
    if chapter.slug == "chapter-19":
        stripped = text.strip()
        if stripped in {
            "Σ0",
            "2 Σ0 4𝜆",
            "B",
            "S nV",
            "n",
            "n )",
            "⎪",
            "⎩",
            "T t=1 Lt",
            "St = 1 + e𝛼t",
            "j=0",
            "( )",
            "[ ]",
            "1e–3",
            "1e–9",
            "1e–7",
            "DATASETS",
            "WHAT IS MICROSTRUCTURAL INFORMATION? 295",
        }:
            return None
        if re.fullmatch(r"[A-Z ]+:\s+[A-Z ]+\s+\d+", stripped):
            return None
        if re.fullmatch(r"\d+\s+[A-Z][A-Z ]+", stripped):
            return None
        if stripped.startswith("The depth and complexity of market microstructure theories"):
            return (
                "<p>The depth and complexity of market microstructure theories has evolved over time, as a function of the amount and variety of the data available. The first generation of models used solely price information. The two foundational results from those early days are trade classification models (like the tick rule) and the Roll [1984] model. The second generation of models came after volume datasets started to become available, and researchers shifted their attention to study the impact that volume has on prices. Two examples for this generation of models are Kyle [1985] and Amihud [2002]. The third generation of models came after 1996, when Maureen O’Hara, David Easley, and others published their “probability of informed trading” (PIN) theory (Easley et al. [1996]). This constituted a major breakthrough, because PIN explained the bid-ask spread as the consequence of a sequential strategic decision between liquidity providers (market makers) and position takers (informed traders). Essentially, it illustrated that market makers were sellers of the option to be adversely selected by informed traders, and the bid-ask spread is the premium they charge for that option. Easley et al. [2012a, 2012b] explain how to estimate VPIN, a high-frequency estimate of PIN under volume-based sampling. These are the main theoretical frameworks used by the microstructural literature. O’Hara [1995] and Hasbrouck [2007] offer a good compendium of low-frequency microstructural models. Easley et al. [2013] present a modern treatment of high-frequency microstructural models.</p>"
            )
        if stripped.startswith("informed traders, and the bid-ask spread"):
            return None
        if stripped.startswith("In a double auction book"):
            return (
                "<p>In a double auction book, quotes are placed for selling a security at various price levels (offers) or for buying a security at various price levels (bids). Offer prices always exceed bid prices, because otherwise there would be an instant match. A trade occurs whenever a buyer matches an offer, or a seller matches a bid. Every trade has a buyer and a seller, but only one side initiates the trade. The tick rule is an algorithm used to determine a trade's aggressor side. A buy-initiated trade is labeled “1”, and a sell-initiated trade is labeled “-1”, according to this logic:</p>"
            )
        if stripped.startswith("Roll [1984] was one of the first models"):
            return (
                "<p>Roll [1984] was one of the first models to propose an explanation for the effective bid-ask spread at which a security trades. This is useful in that bid-ask spreads are a function of liquidity, hence Roll's model can be seen as an early attempt to measure the liquidity of a security. Consider a mid-price series "
                + math_inline(r"\{m_t\}")
                + ", where prices follow a Random Walk with no drift,</p>"
            )
        if stripped.startswith("the liquidity of a security. Consider"):
            return None
        if stripped.startswith("hence price changes Δmt"):
            return (
                "<p>hence price changes "
                + math_inline(r"\Delta m_t=m_t-m_{t-1}")
                + " are independently and identically drawn from a Normal distribution</p>"
            )
        if stripped.startswith("These assumptions are, of course"):
            return (
                "<p>These assumptions are, of course, against all empirical observations, which suggest that financial time series have a drift, they are heteroscedastic, exhibit serial dependency, and their returns distribution is non-Normal. But with a proper sampling procedure, as we saw in Chapter 2, these assumptions may not be too unrealistic. The observed prices, "
                + math_inline(r"\{p_t\}")
                + ", are the result of sequential trading against the bid-ask spread:</p>"
            )
        if stripped.startswith("where pt is the price of the trade indexed"):
            return (
                "<p>where "
                + math_inline("p_t")
                + " is the price of the trade indexed by "
                + math_inline(r"t=1,\ldots,T")
                + ", and "
                + math_inline("b_0")
                + " is arbitrarily set to 1. A number of studies have determined that the tick rule achieves high classification accuracy, despite its relative simplicity (Aitken and Frino [1996]). Competing classification methods include Lee and Ready [1991] and Easley et al. [2016]. Transformations of the "
                + math_inline(r"\{b_t\}")
                + " series can result in informative features. Such transformations include: (1) Kalman filters on its future expected value, "
                + math_inline(r"E_t[b_{t+1}]")
                + "; (2) structural breaks on such predictions (Chapter 17); (3) entropy of the "
                + math_inline(r"\{b_t\}")
                + " sequence (Chapter 18); (4) t-values from Wald-Wolfowitz's tests of runs on "
                + math_inline(r"\{b_t\}")
                + "; (5) fractional differentiation of the cumulative "
                + math_inline(r"\{b_t\}")
                + " series, "
                + math_inline(r"\sum_{i=1}^{t}b_i")
                + " (Chapter 5); etc.</p>"
            )
        if stripped.startswith(("tion accuracy", "differentiation of the cumulative")):
            return None
        if stripped.startswith((
            "chase a price against her interests",
            "position, predatory algorithms",
            "activities, and form a pack",
        )):
            return None
        if stripped.startswith("where c is half the bid-ask spread"):
            return (
                "<p>where "
                + math_inline("c")
                + " is half the bid-ask spread, and "
                + math_inline(r"b_t\in\{-1,1\}")
                + " is the aggressor side. The Roll model assumes that buys and sells are equally likely, "
                + math_inline(r"P[b_t=1]=P[b_t=-1]=\frac{1}{2}")
                + ", serially independent, "
                + math_inline(r"E[b_t b_{t-1}]=0")
                + ", and independent from the noise, "
                + math_inline(r"E[b_t u_t]=0")
                + ". Given these assumptions, Roll derives the values of "
                + math_inline("c")
                + " and "
                + math_inline(r"\sigma_u^2")
                + " as follows:</p>"
            )
        if stripped.startswith("resulting in c = max"):
            return (
                "<p>resulting in "
                + math_inline(r"c=\sqrt{\max\{0,-\sigma[\Delta p_t,\Delta p_{t-1}]\}}")
                + " and "
                + math_inline(r"\sigma_u^2=\sigma^2[\Delta p_t]+2\sigma[\Delta p_t,\Delta p_{t-1}]")
                + ". In conclusion, the bid-ask spread is a function of the serial covariance of price changes, and the true (unobserved) price's noise, excluding microstructural noise, is a function of the observed noise and the serial covariance of price changes.</p>"
            )
        if stripped.startswith("Beckers [1983] shows"):
            return (
                "<p>Beckers [1983] shows that volatility estimators based on high-low prices are more accurate than the standard estimators of volatility based on closing prices. Parkinson [1980] derives that, for continuously observed prices following a geometric Brownian motion,</p>"
            )
        if stripped.startswith("[1980] derives that"):
            return None
        if stripped.startswith("where k1 = 4log"):
            return (
                "<p>where "
                + math_inline(r"k_1=4\log[2]")
                + ", "
                + math_inline(r"k_2=\sqrt{\frac{8}{\pi}}")
                + ", "
                + math_inline("H_t")
                + " is the high price for bar "
                + math_inline("t")
                + ", and "
                + math_inline("L_t")
                + " is the low price for bar "
                + math_inline("t")
                + ". Then the volatility feature "
                + math_inline(r"\sigma_{HL}")
                + " can be robustly estimated based on observed high-low prices.</p>"
            )
        if stripped.startswith("and Ht−1,t is the high price over 2 bars"):
            return (
                "<p>and "
                + math_inline(r"H_{t-1,t}")
                + " is the high price over 2 bars "
                + math_inline(r"(t-1,t)")
                + ", whereas "
                + math_inline(r"L_{t-1,t}")
                + " is the low price over 2 bars "
                + math_inline(r"(t-1,t)")
                + ". Because "
                + math_inline(r"\alpha_t<0\Rightarrow S_t<0")
                + ", the authors recommend setting negative alphas to 0 (see Corwin and Schultz [2012], p. 727). Snippet 19.1 implements this algorithm. The corwinSchultz function receives two arguments, a series dataframe with columns (High, Low), and an integer value "
                + math_inline("sl")
                + " that defines the sample length used to estimate "
                + math_inline(r"\beta_t")
                + ".</p>"
            )
        if stripped.startswith(("alphas to 0", "alpha[alpha<0]=0")):
            return None
        if stripped.startswith("Building on the work of Beckers"):
            return (
                "<p>Building on the work of Beckers [1983], Corwin and Schultz [2012] introduce a bid-ask spread estimator from high and low prices. The estimator is based on two principles: First, high prices are almost always matched against the offer, and low prices are almost always matched against the bid. The ratio of high-to-low prices reflects fundamental volatility as well as the bid-ask spread. Second, the component of the high-to-low price ratio that is due to volatility increases proportionately with the time elapsed between two observations. Corwin and Schultz show that the spread, as a percentage of price, can be estimated as</p>"
            )
        if stripped.startswith("Kyle [1985] introduced"):
            return (
                "<p>Kyle [1985] introduced the following strategic trade model. Consider a risky asset with terminal value "
                + math_inline(r"v\sim N[p_0,\Sigma_0]")
                + ", as well as two traders:</p>"
            )
        if stripped.startswith("The market maker observes the total order flow"):
            return (
                "<p>The market maker observes the total order flow "
                + math_inline(r"y=x+u")
                + ", and sets a price "
                + math_inline("p")
                + " accordingly. In this model, market makers cannot distinguish between orders from noise traders and informed traders. They adjust prices as a function of the order flow imbalance, as that may indicate the presence of an informed trader. Hence, there is a positive relationship between price change and order flow imbalance, which is called market impact. The informed trader conjectures that the market maker has a linear price adjustment function, "
                + math_inline(r"p=\lambda y+\mu")
                + ", where "
                + math_inline(r"\lambda")
                + " is an inverse measure of liquidity. The informed trader's profits are "
                + math_inline(r"\pi=(v-p)x")
                + ", which are maximized at "
                + math_inline(r"x=\frac{v-\mu}{2\lambda}")
                + ", with second order condition "
                + math_inline(r"\lambda>0")
                + ".</p>"
            )
        if stripped.startswith("traders and informed traders"):
            return None
        if stripped.startswith("linear function of v: x = 𝛼"):
            return (
                "<p>Conversely, the market maker conjectures that the informed trader's demand is a linear function of "
                + math_inline("v")
                + ": "
                + math_inline(r"x=\alpha+\beta v")
                + ", which implies "
                + math_inline(r"\alpha=-\frac{\mu}{2\lambda}")
                + " and "
                + math_inline(r"\beta=\frac{1}{2\lambda}")
                + ". Note that lower liquidity means higher "
                + math_inline(r"\lambda")
                + ", which means lower demand from the informed trader. Kyle argues that the market maker must find an equilibrium between profit maximization and market efficiency, and that under the above linear functions, the only possible solution occurs when</p>"
            )
        if stripped.startswith("In Kyle’s model"):
            return (
                "<p>In Kyle's model, the variable "
                + math_inline(r"\lambda")
                + " captures price impact. Illiquidity increases with uncertainty about "
                + math_inline("v")
                + " and decreases with the amount of noise. As a feature, it can be estimated by fitting the regression</p>"
            )
        if stripped.startswith("where {pt } is the time series of prices"):
            return (
                "<p>where "
                + math_inline(r"\{p_t\}")
                + " is the time series of prices, "
                + math_inline(r"\{b_t\}")
                + " is the time series of aggressor flags, "
                + math_inline(r"\{V_t\}")
                + " is the time series of traded volumes, and hence "
                + math_inline(r"\{b_tV_t\}")
                + " is the time series of signed volume or net order flow. Figure 19.1 plots the histogram of Kyle's lambdas estimated on the E-mini S&P 500 futures series.</p>"
            )
        if stripped.startswith("where B𝜏 is the set of trades included"):
            return (
                "<p>where "
                + math_inline(r"B_{\tau}")
                + " is the set of trades included in bar "
                + math_inline(r"\tau")
                + ", "
                + math_inline(r"\tilde p_{\tau}")
                + " is the closing price of bar "
                + math_inline(r"\tau")
                + ", and "
                + math_inline(r"p_tV_t")
                + " is the dollar volume involved in trade "
                + math_inline(r"t\in B_{\tau}")
                + ". Despite its apparent simplicity, Hasbrouck [2009] found that daily Amihud's lambda estimates exhibit a high rank correlation to intraday estimates of effective spread. Figure 19.2 plots the histogram of Amihud's lambdas estimated on the E-mini S&P 500 futures series.</p>"
            )
        if stripped.startswith("correlation to intraday estimates"):
            return None
        if stripped.startswith("where Bi,𝜏 is the set of trades included"):
            return (
                "<p>where "
                + math_inline(r"B_{i,\tau}")
                + " is the set of trades included in bar "
                + math_inline(r"\tau")
                + " for security "
                + math_inline("i")
                + ", with "
                + math_inline(r"i=1,\ldots,I")
                + ", "
                + math_inline(r"\tilde p_{i,\tau}")
                + " is the closing price of bar "
                + math_inline(r"\tau")
                + " for security "
                + math_inline("i")
                + ", "
                + math_inline(r"b_{i,t}\in\{-1,1\}")
                + " indicates whether trade "
                + math_inline(r"t\in B_{i,\tau}")
                + " was buy-initiated or sell-initiated; and "
                + math_inline(r"p_{i,t}V_{i,t}")
                + " is the dollar volume involved in trade "
                + math_inline(r"t\in B_{i,\tau}")
                + ". We can then estimate "
                + math_inline(r"\lambda_i")
                + " for every security "
                + math_inline("i")
                + ", and use it as a feature that approximates the effective cost of trading (market impact). Consistent with most of the literature, Hasbrouck recommends 5-minute time-bars for sampling ticks. However, for the reasons discussed in Chapter 2, better results can be achieved through stochastic sampling methods that are synchronized with market activity. Figure 19.3 plots the histogram of Hasbrouck's lambdas estimated on the E-mini S&P 500 futures series.</p>"
            )
        if stripped.startswith("Easley et al. [1996] use trade data"):
            return (
                "<p>Easley et al. [1996] use trade data to determine the probability of information-based trading (PIN) of individual securities. This microstructure model views trading as a game between market makers and position takers that is repeated over multiple trading periods. Denote a security's price as "
                + math_inline("S")
                + ", with present value "
                + math_inline("S_0")
                + ". However, once a certain amount of new information has been incorporated into the price, "
                + math_inline("S")
                + " will be either "
                + math_inline("S_B")
                + " (bad news) or "
                + math_inline("S_G")
                + " (good news). There is a probability "
                + math_inline(r"\alpha")
                + " that new information will arrive within the timeframe of the analysis, a probability "
                + math_inline(r"\delta")
                + " that the news will be bad, and a probability "
                + math_inline(r"1-\delta")
                + " that the news will be good. These authors prove that the expected value of the security's price can then be computed at time "
                + math_inline("t")
                + " as</p>"
            )
        if stripped.startswith("and a probability (1"):
            return None
        if stripped.startswith("Following a Poisson distribution"):
            return (
                "<p>Following a Poisson distribution, informed traders arrive at a rate "
                + math_inline(r"\mu")
                + ", and uninformed traders arrive at a rate "
                + math_inline(r"\varepsilon")
                + ". Then, in order to avoid losses from informed traders, market makers reach breakeven at a bid level "
                + math_inline("B_t")
                + ",</p>"
            )
        if stripped.startswith("and the breakeven ask level"):
            return "<p>and the breakeven ask level " + math_inline("A_t") + " at time " + math_inline("t") + " must be,</p>"
        if stripped.startswith("It follows that the breakeven bid-ask spread"):
            return "<p>It follows that the breakeven bid-ask spread is determined as</p>"
        if stripped.startswith("For the standard case when 𝛿t"):
            return "<p>For the standard case when " + math_inline(r"\delta_t=\frac{1}{2}") + ", we obtain</p>"
        if stripped.startswith("The subscript t indicates"):
            return (
                "<p>The subscript "
                + math_inline("t")
                + " indicates that the probabilities "
                + math_inline(r"\alpha")
                + " and "
                + math_inline(r"\delta")
                + " are estimated at that point in time. The authors apply a Bayesian updating process to incorporate information after each trade arrives to the market.</p>"
                "<p>In order to determine the value "
                + math_inline("PIN_t")
                + ", we must estimate four non-observable parameters, namely "
                + math_inline(r"\{\alpha,\delta,\mu,\varepsilon\}")
                + ". A maximum-likelihood approach is to fit a mixture of three Poisson distributions,</p>"
            )
        if stripped.startswith("where V B is the volume traded"):
            return "<p>where " + math_inline(r"V^B") + " is the volume traded against the ask (buy-initiated trades), and " + math_inline(r"V^S") + " is the volume traded against the bid (sell-initiated trades).</p>"
        if stripped.startswith("Easley et al. [2008] proved"):
            return "<p>Easley et al. [2008] proved that</p>"
        if stripped.startswith("where V𝜏B is the sum"):
            return (
                "<p>where "
                + math_inline(r"V_\tau^B")
                + " is the sum of volumes from buy-initiated trades within volume bar "
                + math_inline(r"\tau")
                + ", "
                + math_inline(r"V_\tau^S")
                + " is the sum of volumes from sell-initiated trades within volume bar "
                + math_inline(r"\tau")
                + ", and "
                + math_inline("n")
                + " is the number of bars used to produce this estimate. Because all volume bars are of the same size, "
                + math_inline("V")
                + ", we know that by construction</p>"
            )
        if stripped.startswith("Easley et al. [2016] study the frequency"):
            return (
                "<p>Easley et al. [2016] study the frequency of trades per trade size, and find that trades with round sizes are abnormally frequent. For example, the frequency rates quickly decay as a function of trade size, with the exception of round trade sizes "
                + math_inline(r"\{5,10,20,25,50,100,200,\ldots\}")
                + ". These authors attribute this phenomenon to so-called “mouse” or “GUI” traders, that is, human traders who send orders by clicking buttons on a GUI (Graphical User Interface). In the case of the E-mini S&P 500, for example, size 10 is 2.9 times more frequent than size 9; size 50 is 10.9 times more likely than size 49; size 100 is 16.8 times more frequent than size 99; size 200 is 27.2 times more likely than size 199; size 250 is 32.5 times more frequent than size 249; size 500 is 57.1 times more frequent than size 499. Such patterns are not typical of “silicon traders,” who usually are programmed to randomize trades to disguise their footprint in markets. A useful feature may be to determine the normal frequency of round-sized trades, and monitor deviations from that expected value. The ML algorithm could, for example, determine if a larger-than-usual proportion of round-sized trades is associated with trends, as human traders tend to bet with a fundamental view, belief, or conviction. Conversely, a lower-than-usual proportion of round-sized trades may increase the likelihood that prices will move sideways, as silicon traders do not typically hold long-term views.</p>"
            )
        if stripped.startswith("Consider a features matrix X"):
            return (
                "<p>Consider a features matrix "
                + math_inline(r"X=\{X_t\}_{t=1,\ldots,T}")
                + " that contains information typically used by market makers to determine whether they should provide liquidity at a particular level, or cancel their passive quotes. For example, the columns could be all of the features discussed in this chapter, like VPIN, Kyle's lambda, cancellation rates, etc. Matrix "
                + math_inline("X")
                + " has one row for each decision point. For example, a market maker may reconsider the decision to either provide liquidity or pull out of the market every time 10,000 contracts are traded, or whenever there is a significant change in prices (recall sampling methods in Chapter 2), etc. First, we derive an array "
                + math_inline(r"y=\{y_t\}_{t=1,\ldots,T}")
                + " that assigns a label 1 to an observation that resulted in a market-making profit, and labels as 0 an observation that resulted in a market-making loss (see Chapter 3 for labeling methods). Second, we fit a classifier on the training set "
                + math_inline(r"(X,y)")
                + ". Third, as new out-of-sample observations arrive "
                + math_inline(r"\tau>T")
                + ", we use the fit classifier to predict the label "
                + math_inline(r"\hat y_\tau=E_\tau[y_\tau\mid X]")
                + ". Fourth, we derive the cross-entropy loss of these predictions, "
                + math_inline(r"L_\tau")
                + ", as described in Chapter 9, Section 9.4. Fifth, we fit a kernel density estimator (KDE) on the array of negative cross-entropy losses, "
                + math_inline(r"\{-L_t\}_{t=T+1,\ldots,\tau}")
                + ", to derive its cumulative distribution function, "
                + math_inline("F")
                + ". Sixth, we estimate the microstructural information at time "
                + math_inline("t")
                + " as "
                + math_inline(r"\phi_\tau=F[-L_\tau]")
                + ", where "
                + math_inline(r"\phi_\tau\in(0,1)")
                + ".</p>"
            )
        if stripped.startswith("This microstructural information can be understood"):
            return (
                "<p>This microstructural information can be understood as the complexity faced by market makers' decision models. Under normal market conditions, market makers produce informed forecasts with low cross-entropy loss, and are able to profit from providing liquidity to position takers. However, in the presence of (asymmetrically) informed traders, market makers produce uninformed forecasts, as measured by high cross-entropy loss, and they are adversely selected. In other words, microstructural information can only be defined and measured relative to the predictive power of market makers. The implication is that "
                + math_inline(r"\{\phi_\tau\}")
                + " should become an important feature in your financial ML toolkit.</p>"
                "<p>Consider the events of the flash crash of May 6, 2010. Market makers wrongly predicted that their passive quotes sitting on the bid could be filled and sold back at a higher level. The crash was not caused by a single inaccurate prediction, but by the accumulation of thousands of prediction errors (Easley et al. [2011]). If market makers had monitored the rising cross-entropy loss of their predictions, they would have recognized the presence of informed traders and the dangerously rising probability of adverse selection. That would have allowed them to widen the bid-ask spread to levels that would have stopped the order flow imbalance, as sellers would no longer have been willing to sell at those discounts. Instead, market makers kept providing liquidity to sellers at exceedingly generous levels, until eventually they were forced to stop-out, triggering a liquidity crisis that shocked markets, regulators, and academics for months and years.</p>"
            )
        if stripped.startswith("1 Σ0 𝜆="):
            return math_display(r"\lambda=\frac{1}{2}\sqrt{\frac{\Sigma_0}{\sigma_u^2}}")
        if stripped == "PINt =":
            return math_display(r"PIN_t=\frac{\alpha_t\mu}{\alpha_t\mu+2\varepsilon}")
        if stripped.startswith("log ̃pi,𝜏"):
            return math_display(r"\log[\tilde p_{i,\tau}]-\log[\tilde p_{i,\tau-1}]=\lambda_i\sum_{t\in B_{i,\tau}}b_{i,t}\sqrt{p_{i,t}V_{i,t}}+\varepsilon_{i,\tau}")
    if chapter.slug == "chapter-15":
        stripped = text.strip()
        if re.fullmatch(r"[⏟⏞⏝\s]+", stripped):
            return None
        if stripped in {"1 n", "p= 2a", "cies (n)"}:
            return None
        if stripped.startswith("As we saw in Chapters 3 and 13"):
            return "<p>" + mathify_general_text(stripped.replace("stoploss", "stop-loss")) + "</p>"
        if stripped.startswith("Consider a strategy that produces n IID bets per year, where the outcome Xi of a") and "profit 𝜋" in stripped:
            return (
                "<p>Consider a strategy that produces "
                r'<span class="math inline">\(n\)</span>'
                " IID bets per year, where the outcome "
                r'<span class="math inline">\(X_i\)</span>'
                " of a bet "
                r'<span class="math inline">\(i\in[1,n]\)</span>'
                " is a profit "
                r'<span class="math inline">\(\pi>0\)</span>'
                " with probability "
                r'<span class="math inline">\(P[X_i=\pi]=p\)</span>'
                ", and a loss "
                r'<span class="math inline">\(-\pi\)</span>'
                " with probability "
                r'<span class="math inline">\(P[X_i=-\pi]=1-p\)</span>'
                ". You can think of "
                r'<span class="math inline">\(p\)</span>'
                " as the precision of a binary classifier where a positive means betting on an opportunity, and a negative means passing on an opportunity: True positives are rewarded, false positives are punished, and negatives (whether true or false) have no payout. Since the betting outcomes "
                r'<span class="math inline">\(\{X_i\}_{i=1,\ldots,n}\)</span>'
                " are independent, we will compute the expected moments per bet. The expected profit from one bet is "
                r'<span class="math inline">\(\mathbb{E}[X_i]=\pi p+(-\pi)(1-p)=\pi(2p-1)\)</span>'
                ". The variance is "
                r'<span class="math inline">\(\mathbb{V}[X_i]=\mathbb{E}[X_i^2]-\mathbb{E}[X_i]^2\)</span>'
                ", where "
                r'<span class="math inline">\(\mathbb{E}[X_i^2]=\pi^2p+(-\pi)^2(1-p)=\pi^2\)</span>'
                ", thus</p>"
            )
        if stripped.startswith("V[Xi ] = 𝜋 2"):
            return (
                "<p>"
                r'<span class="math inline">\(\mathbb{V}[X_i]=\pi^2-\pi^2(2p-1)^2=\pi^2[1-(2p-1)^2]=4\pi^2p(1-p)\)</span>'
                ". For "
                r'<span class="math inline">\(n\)</span>'
                " IID bets per year, the annualized Sharpe ratio "
                r'<span class="math inline">\((\theta)\)</span>'
                " is</p>"
            )
        if stripped.startswith("Note how 𝜋 cancels"):
            return (
                "<p>Note how "
                + math_inline(r"\pi")
                + " cancels out of the above equation, because the payouts are symmetric. Just as in the Gaussian case, "
                + math_inline(r"\theta[p,n]")
                + " can be understood as a re-scaled t-value. This illustrates the point that, even for a small "
                + math_inline(r"p>\frac{1}{2}")
                + ", the Sharpe ratio can be made high for a sufficiently large "
                + math_inline("n")
                + ". This is the economic basis for high-frequency trading, where "
                + math_inline("p")
                + " can be barely above .5, and the key to a successful business is to increase "
                + math_inline("n")
                + ". The Sharpe ratio is a function of precision rather than accuracy, because passing on an opportunity (a negative) is not rewarded or punished directly (although too many negatives may lead to a small "
                + math_inline("n")
                + ", which will depress the Sharpe ratio toward zero).</p>"
            )
        if stripped.startswith("For example, for p = .55"):
            return (
                "<p>For example, for "
                r'<span class="math inline">\(p=.55\)</span>'
                ", "
                r'<span class="math inline">\(\frac{2p-1}{2\sqrt{p(1-p)}}=0.1005\)</span>'
                ", and achieving an annualized Sharpe ratio of 2 requires 396 bets per year. "
                "Snippet 15.1 verifies this result experimentally. Figure 15.1 plots the Sharpe ratio as a function of precision, for various betting frequencies.</p>"
            )
        if stripped.startswith("ratio of 2 requires 396 bets per year"):
            return None
        if stripped.startswith("Solving for 0 ≤ p ≤ 1"):
            return (
                "<p>Solving for "
                r'<span class="math inline">\(0\le p\le1\)</span>'
                ", we obtain "
                r'<span class="math inline">\(-4p^2+4p-\frac{n}{\theta^2+n}=0\)</span>'
                ", with solution</p>"
            )
        if stripped.startswith("This equation makes explicit the trade-off between precision"):
            return (
                "<p>This equation makes explicit the trade-off between precision "
                r'<span class="math inline">\((p)\)</span>'
                " and frequency "
                r'<span class="math inline">\((n)\)</span>'
                " for a given Sharpe ratio "
                r'<span class="math inline">\((\theta)\)</span>'
                ". For example, a strategy that only produces weekly bets "
                r'<span class="math inline">\((n=52)\)</span>'
                " will need a fairly high precision of "
                r'<span class="math inline">\(p=0.6336\)</span>'
                " to deliver an annualized Sharpe of 2.</p>"
            )
        if stripped.startswith("Consider a strategy that produces n IID bets per year, where the outcome Xi") and "𝜋+" in stripped:
            return (
                "<p>Consider a strategy that produces "
                r'<span class="math inline">\(n\)</span>'
                " IID bets per year, where the outcome "
                r'<span class="math inline">\(X_i\)</span>'
                " of a bet "
                r'<span class="math inline">\(i\in[1,n]\)</span>'
                " is "
                r'<span class="math inline">\(\pi_+\)</span>'
                " with probability "
                r'<span class="math inline">\(P[X_i=\pi_+]=p\)</span>'
                ", and an outcome "
                r'<span class="math inline">\(\pi_-\)</span>'
                ", "
                + math_inline(r"\pi_-<\pi_+")
                + " occurs with probability "
                r'<span class="math inline">\(P[X_i=\pi_-]=1-p\)</span>'
                ". The expected profit from one bet is "
                r'<span class="math inline">\(\mathbb{E}[X_i]=p\pi_++(1-p)\pi_-=(\pi_+-\pi_-)p+\pi_-\)</span>'
                ". The variance is "
                r'<span class="math inline">\(\mathbb{V}[X_i]=\mathbb{E}[X_i^2]-\mathbb{E}[X_i]^2\)</span>'
                ", where "
                r'<span class="math inline">\(\mathbb{E}[X_i^2]=p\pi_+^2+(1-p)\pi_-^2=(\pi_+^2-\pi_-^2)p+\pi_-^2\)</span>'
                ", thus "
                r'<span class="math inline">\(\mathbb{V}[X_i]=(\pi_+-\pi_-)^2p(1-p)\)</span>'
                ". For "
                r'<span class="math inline">\(n\)</span>'
                " IID bets per year, the annualized Sharpe ratio "
                r'<span class="math inline">\((\theta)\)</span>'
                " is</p>"
            )
        if stripped.startswith("And for 𝜋− = −𝜋+"):
            return (
                "<p>And for "
                r'<span class="math inline">\(\pi_-=-\pi_+\)</span>'
                " we can see that this equation reduces to the symmetric case:</p>"
            )
        if stripped.startswith("Finally, we can solve the previous equation"):
            return (
                "<p>Finally, we can solve the previous equation for "
                + math_inline(r"0\le p\le1")
                + ", to obtain</p>"
            )
        if stripped.startswith("As a side note, Snippet 15.2"):
            return (
                '<p>As a side note, Snippet 15.2 verifies these symbolic operations using '
                'SymPy Live: <a href="http://live.sympy.org/">http://live.sympy.org/</a>.</p>'
            )
        if stripped.startswith("case: 𝜃[p, n, −𝜋+ , 𝜋+ ]"):
            return (
                "<p>For example, for "
                r'<span class="math inline">\(n=260\)</span>'
                ", "
                r'<span class="math inline">\(\pi_-=-.01\)</span>'
                ", "
                r'<span class="math inline">\(\pi_+=.005\)</span>'
                ", "
                r'<span class="math inline">\(p=.7\)</span>'
                ", we get "
                r'<span class="math inline">\(\theta=1.173\)</span>'
                ".</p>"
            )
        if stripped.startswith("The above equation answers the following question"):
            return (
                "<p>The above equation answers the following question: Given a trading rule characterized by parameters "
                r'<span class="math inline">\(\{\pi_-,\pi_+,n\}\)</span>'
                ", what is the precision rate "
                r'<span class="math inline">\(p\)</span>'
                " required to achieve a Sharpe ratio of "
                r'<span class="math inline">\(\theta^*\)</span>'
                "? For example, for "
                r'<span class="math inline">\(n=260\)</span>'
                ", "
                r'<span class="math inline">\(\pi_-=-.01\)</span>'
                ", "
                r'<span class="math inline">\(\pi_+=.005\)</span>'
                ", in order to get "
                r'<span class="math inline">\(\theta=2\)</span>'
                " we require "
                r'<span class="math inline">\(p=.72\)</span>'
                ". Thanks to the large number of bets, a very small change in "
                r'<span class="math inline">\(p\)</span>'
                " (from "
                r'<span class="math inline">\(p=.7\)</span>'
                " to "
                r'<span class="math inline">\(p=.72\)</span>'
                ") has propelled the Sharpe ratio from "
                r'<span class="math inline">\(\theta=1.173\)</span>'
                " to "
                r'<span class="math inline">\(\theta=2\)</span>'
                ". On the other hand, this also tells us that the strategy is vulnerable to small changes in "
                r'<span class="math inline">\(p\)</span>'
                ". Snippet 15.3 implements the derivation of the implied precision. Figure 15.2 displays the implied precision as a function of "
                r'<span class="math inline">\(n\)</span>'
                " and "
                r'<span class="math inline">\(\pi_-\)</span>'
                ", where "
                r'<span class="math inline">\(\pi_+=0.1\)</span>'
                " and "
                r'<span class="math inline">\(\theta^*=1.5\)</span>'
                ". As "
                r'<span class="math inline">\(\pi_-\)</span>'
                " becomes more negative for a given "
                r'<span class="math inline">\(n\)</span>'
                ", a higher "
                r'<span class="math inline">\(p\)</span>'
                " is required to achieve "
                r'<span class="math inline">\(\theta^*\)</span>'
                " for a given "
                r'<span class="math inline">\(\pi_+\)</span>'
                ". As "
                r'<span class="math inline">\(n\)</span>'
                " becomes smaller for a given "
                r'<span class="math inline">\(\pi_-\)</span>'
                ", a higher "
                r'<span class="math inline">\(p\)</span>'
                " is required to achieve "
                r'<span class="math inline">\(\theta^*\)</span>'
                " for a given "
                r'<span class="math inline">\(\pi_+\)</span>'
                ".</p>"
                + chapter_15_figure_html("15.2")
            )
        if stripped.startswith("Snippet 15.4 solves"):
            return (
                "<p>Snippet 15.4 solves "
                r'<span class="math inline">\(\theta[p,n,\pi_-,\pi_+]\)</span>'
                " for the implied betting frequency, "
                r'<span class="math inline">\(n\)</span>'
                ". Figure 15.3 plots the implied frequency as a function of "
                r'<span class="math inline">\(p\)</span>'
                " and "
                r'<span class="math inline">\(\pi_-\)</span>'
                ", where "
                r'<span class="math inline">\(\pi_+=0.1\)</span>'
                " and "
                r'<span class="math inline">\(\theta^*=1.5\)</span>'
                ". As "
                r'<span class="math inline">\(\pi_-\)</span>'
                " becomes more negative for a given "
                r'<span class="math inline">\(p\)</span>'
                ", a higher "
                r'<span class="math inline">\(n\)</span>'
                " is required to achieve "
                r'<span class="math inline">\(\theta^*\)</span>'
                " for a given "
                r'<span class="math inline">\(\pi_+\)</span>'
                ". As "
                r'<span class="math inline">\(p\)</span>'
                " becomes smaller for a given "
                r'<span class="math inline">\(\pi_-\)</span>'
                ", a higher "
                r'<span class="math inline">\(n\)</span>'
                " is required to achieve "
                r'<span class="math inline">\(\theta^*\)</span>'
                " for a given "
                r'<span class="math inline">\(\pi_+\)</span>'
                ".</p>"
                + chapter_15_figure_html("15.3")
            )
        if stripped.startswith("In the example above, parameters"):
            return (
                "<p>In the example above, parameters "
                r'<span class="math inline">\(\pi_-=-.01\)</span>'
                ", "
                r'<span class="math inline">\(\pi_+=.005\)</span>'
                " are set by the portfolio manager, and passed to the traders with the execution orders. Parameter "
                r'<span class="math inline">\(n=260\)</span>'
                " is also set by the portfolio manager, as she decides what constitutes an opportunity worth betting on. The two parameters that are not under the control of the portfolio manager are "
                r'<span class="math inline">\(p\)</span>'
                " (determined by the market) and "
                r'<span class="math inline">\(\theta^*\)</span>'
                " (the objective set by the investor). Because "
                r'<span class="math inline">\(p\)</span>'
                " is unknown, we can model it as a random variable, with expected value "
                r'<span class="math inline">\(\mathbb{E}[p]\)</span>'
                ". Let us define "
                r'<span class="math inline">\(p_{\theta^*}\)</span>'
                " as the value of "
                r'<span class="math inline">\(p\)</span>'
                " below which the strategy will underperform a target Sharpe ratio "
                r'<span class="math inline">\(\theta^*\)</span>'
                ", that is, "
                r'<span class="math inline">\(p_{\theta^*}=\max\{p\mid\theta\le\theta^*\}\)</span>'
                ". We can use the equations above (or the binHR function) to conclude that for "
                r'<span class="math inline">\(p_{\theta^*=0}=\frac{2}{3}\)</span>'
                ", "
                + math_inline(r"p<p_{\theta^*=0}\Rightarrow\theta\le0")
                + ".</p>"
            )
        if stripped.startswith("the risks involved in this strategy"):
            return (
                "<p>This highlights the risks involved in this strategy, because a relatively small drop in "
                + math_inline("p")
                + " (from "
                + math_inline("p=.7")
                + " to "
                + math_inline("p=.67")
                + ") will wipe out all the profits. The strategy is intrinsically risky, even if the holdings are not. That is the critical difference we wish to establish with this chapter: Strategy risk should not be confused with portfolio risk. Most firms and investors compute, monitor, and report portfolio risk without realizing that this tells us nothing about the risk of the strategy itself. Strategy risk is not the risk of the underlying portfolio, as computed by the chief risk officer. Strategy risk is the risk that the investment strategy will fail to succeed over time, a question of far greater relevance to the chief investment officer. The answer to the question “What is the probability that this strategy will fail?” is equivalent to computing "
                + math_inline(r"P[p<p_{\theta^*}]")
                + ". The following algorithm will help us compute the strategy risk.</p>"
            )
        if stripped.startswith("Strategy risk is not the risk of the underlying portfolio"):
            return (
                "<p>Strategy risk is not the risk of the underlying portfolio, as computed by the chief risk officer. Strategy risk is the risk that the investment strategy will fail to succeed over time, a question of far greater relevance to the chief investment officer. The answer to the question “What is the probability that this strategy will fail?” is equivalent to computing "
                + math_inline(r"P[p<p_{\theta^*}]")
                + ". The following algorithm will help us compute the strategy risk.</p>"
            )
        if stripped.startswith("In this section we will describe a procedure"):
            return (
                "<p>In this section we will describe a procedure to compute "
                + math_inline(r"P[p<p_{\theta^*}]")
                + ". Given a time series of bet outcomes "
                r'<span class="math inline">\(\{\pi_t\}_{t=1,\ldots,T}\)</span>'
                ", first we estimate "
                r'<span class="math inline">\(\pi_-=\mathbb{E}[\{\pi_t\mid\pi_t\le0\}_{t=1,\ldots,T}]\)</span>'
                ", and "
                r'<span class="math inline">\(\pi_+=\mathbb{E}[\{\pi_t\mid\pi_t>0\}_{t=1,\ldots,T}]\)</span>'
                ". Alternatively, "
                r'<span class="math inline">\(\{\pi_-,\pi_+\}\)</span>'
                " could be derived from fitting a mixture of two Gaussians, using the EF3M algorithm (López de Prado and Foreman "
                "[2014]"
                "). Second, the annual frequency "
                r'<span class="math inline">\(n\)</span>'
                " is given by "
                r'<span class="math inline">\(n=\frac{T}{y}\)</span>'
                ", where "
                r'<span class="math inline">\(y\)</span>'
                " is the number of years elapsed between "
                r'<span class="math inline">\(t=1\)</span>'
                " and "
                r'<span class="math inline">\(t=T\)</span>'
                ". Third, we bootstrap the distribution of "
                r'<span class="math inline">\(p\)</span>'
                " as follows:</p>"
            )
        if stripped.startswith("For a sufficiently large k"):
            return (
                "<p>For a sufficiently large "
                r'<span class="math inline">\(k\)</span>'
                ", we can approximate this third step as "
                r'<span class="math inline">\(f[p]\sim N[\bar p,\bar p(1-\bar p)]\)</span>'
                ", where "
                r'<span class="math inline">\(\bar p=\mathbb{E}[p]=\frac{1}{T}\left\|\{\pi_t^{(i)}\mid\pi_t^{(i)}>0\}_{t=1,\ldots,T}\right\|\)</span>'
                ". Fourth, given a threshold "
                r'<span class="math inline">\(\theta^*\)</span>'
                " (the Sharpe ratio that separates failure from success), derive "
                r'<span class="math inline">\(p_{\theta^*}\)</span>'
                " (see Section 15.4). Fifth, the strategy risk is computed as</p>"
                + math_display(r"\mathbb{P}[p<p_{\theta^*}]=\int_{-\infty}^{p_{\theta^*}} f[p]\,dp")
            )
        if stripped.startswith("tion 15.4). Fifth"):
            return None
        if stripped.startswith("Snippet 15.5 lists"):
            return (
                "<p>Snippet 15.5 lists one possible implementation of this algorithm. Typically we would disregard strategies where "
                + math_inline(r"P[p<p_{\theta^*}]>.05")
                + " as too risky, even if they invest in low volatility instruments. The reason is that even if they do not lose much money, the probability that they will fail to achieve their target is too high. In order to be deployed, the strategy developer must find a way to reduce "
                r'<span class="math inline">\(p_{\theta^*}\)</span>'
                ".</p>"
            )
        if stripped.startswith("This approach shares some similarities with PSR"):
            return (
                "<p>This approach shares some similarities with "
                + math_inline(r"\mathrm{PSR}")
                + " (see Chapter 14, and Bailey and López de Prado [2012, 2014]). "
                + math_inline(r"\mathrm{PSR}")
                + " derives the probability that the true Sharpe ratio exceeds a given threshold under non-Gaussian returns. Similarly, the method introduced in this chapter derives the strategy’s probability of failure based on asymmetric binary outcomes. The key difference is that, while "
                + math_inline(r"\mathrm{PSR}")
                + " does not distinguish between parameters under or outside the portfolio manager’s control, the method discussed here allows the portfolio manager to study the viability of the strategy subject to the parameters under her control: "
                + math_inline(r"\{\pi_-,\pi_+,n\}")
                + ". This is useful when designing or assessing the viability of a trading strategy.</p>"
            )
    if chapter.slug == "chapter-02":
        text = text.replace("Chapters 17– 19", "Chapters 17–19")
        if is_chapter_02_artifact(text):
            return None
        if text.startswith("Financial data comes in many shapes and forms. Table 2.1"):
            return (
                f"<p>{mathify_chapter_02_text(text)}</p>"
                '<figure class="table-figure"><figcaption>Table 2.1: The Four Essential Types of Financial Data</figcaption>'
                f'<div class="table-wrap">{table_2_1_html()}</div></figure>'
            )
        if text.startswith("Fundamental data encompasses information that can be found in regulatory filings"):
            return (
                "<p>Fundamental data encompasses information that can be found in regulatory filings and business analytics. "
                "It is mostly accounting data, reported quarterly. A particular aspect of this data is that it is reported with a lapse. "
                "You must confirm exactly when each data point was released, so that your analysis uses that information only after it was publicly available. "
                "A common beginner's error is to assume that this data was published at the end of the reporting period. That is never the case.</p>"
                "<p>For example, fundamental data published by Bloomberg is indexed by the last date included in the report, which precedes the date of the release (often by 1.5 months). "
                "In other words, Bloomberg is assigning those values to a date when they were not known. You could not believe how many papers are published every year using misaligned fundamental data, especially in the factor-investing literature. "
                "Once you align the data correctly, a substantial number of findings in those papers cannot be reproduced.</p>"
                "<p>A second aspect of fundamental data is that it is often backfilled or reinstated. "
                "“Backfilling” means that missing data is assigned a value, even if those values were unknown at that time. "
                "A “reinstated value” is a corrected value that amends an incorrect initial release. "
                "A company may issue multiple corrections for a past quarter's results long after the first publication, and data vendors may overwrite the initial values with their corrections. "
                "The problem is, the corrected values were not known on that first release date. "
                "Some data vendors circumvent this problem by storing multiple release dates and values for each variable. "
                "For example, we typically have three values for a single quarterly GDP release: the original released value and two monthly revisions. "
                "Still, it is very common to find studies that use the final released value and assign it to the time of the first release, or even to the last day in the reporting period. "
                "We will revisit this mistake, and its implications, when we discuss backtesting errors in Chapter 11.</p>"
                "<p>Fundamental data is extremely regularized and low frequency. Being so accessible to the marketplace, it is rather unlikely that there is much value left to be exploited. "
                "Still, it may be useful in combination with other data types.</p>"
            )
        if text.startswith("fundamental data, especially in the factor-investing literature"):
            return None
        if text.startswith("Second, we compute the expected value of 𝜃T at the beginning of the bar, E0 [𝜃T ] ="):
            return (
                "<p>Second, we compute the expected value of "
                r'<span class="math inline">\(\theta_T\)</span>'
                " at the beginning of the bar, "
                r'<span class="math inline">\(\mathbb{E}_0[\theta_T]=\mathbb{E}_0[T](P[b_t=1]-P[b_t=-1])\)</span>'
                ", where "
                r'<span class="math inline">\(\mathbb{E}_0[T]\)</span>'
                " is the expected size of the tick bar, "
                r'<span class="math inline">\(P[b_t=1]\)</span>'
                " is the unconditional probability that a tick is classified as a buy, and "
                r'<span class="math inline">\(P[b_t=-1]\)</span>'
                " is the unconditional probability that a tick is classified as a sell. Since "
                r'<span class="math inline">\(P[b_t=1]+P[b_t=-1]=1\)</span>'
                ", then</p>"
            )
        if text.startswith("The purpose of 𝜔i,t"):
            return (
                "<p>The purpose of "
                r'<span class="math inline">\(\omega_{i,t}(\sum_{i=1}^{I}|\omega_{i,t}|)^{-1}\)</span>'
                " in "
                r'<span class="math inline">\(h_{i,t}\)</span>'
                " is to de-lever the allocations. For series of futures, we may not know "
                r'<span class="math inline">\(p_{i,t}\)</span>'
                " of the new contract at a roll time "
                r'<span class="math inline">\(t\)</span>'
                ", so we use "
                r'<span class="math inline">\(o_{i,t+1}\)</span>'
                " as the closest in time.</p>"
                "<p>Let "
                r'<span class="math inline">\(\tau_i\)</span>'
                " be the transaction cost associated with trading $1 of instrument "
                r'<span class="math inline">\(i\)</span>'
                ", e.g., "
                r'<span class="math inline">\(\tau_i=1E-4\)</span>'
                " (one basis point). There are three additional variables that the strategy needs to know for every observed bar "
                r'<span class="math inline">\(t\)</span>'
                ":</p>"
            )
        if text.startswith("can estimate E0 [T]"):
            return "<p>" + mathify_chapter_02_text("we " + text) + "</p>"
        if text.startswith("that E0 [T]−1"):
            return (
                "<p>You can think of "
                r'<span class="math inline">\(v^+\)</span>'
                " and "
                r'<span class="math inline">\(v^-\)</span>'
                " as decomposing the initial expectation of "
                r'<span class="math inline">\(v_t\)</span>'
                " into the component contributed by buys and the component contributed by sells. Then</p>"
            )
        if text.startswith("where the expected count of ticks from runs is implied by"):
            return (
                "<p>where the expected count of ticks from runs is implied by "
                r'<span class="math inline">\(\max\{P[b_t=1],1-P[b_t=1]\}\)</span>'
                ". When "
                r'<span class="math inline">\(\theta_T\)</span>'
                " exhibits more runs than expected, a low "
                r'<span class="math inline">\(T\)</span>'
                " will satisfy these conditions. Note that in this definition of runs we allow for sequence breaks. "
                "That is, instead of measuring the length of the longest sequence, we count the number of ticks of each side, without offsetting them (no imbalance). "
                "In the context of forming bars, this turns out to be a more useful definition than measuring sequence lengths.</p>"
            )
        if text.startswith("and K0 = 1 in the initial AUM"):
            return (
                "<p>and "
                r'<span class="math inline">\(K_0=1\)</span>'
                " in the initial AUM. Variable "
                r'<span class="math inline">\(h_{i,t}\)</span>'
                " represents the holdings (number of securities or contracts) of instrument "
                r'<span class="math inline">\(i\)</span>'
                " at time "
                r'<span class="math inline">\(t\)</span>'
                ". Variable "
                r'<span class="math inline">\(\delta_{i,t}\)</span>'
                " is the change of market value between "
                r'<span class="math inline">\(t-1\)</span>'
                " and "
                r'<span class="math inline">\(t\)</span>'
                " for instrument "
                r'<span class="math inline">\(i\)</span>'
                ". Note that profits or losses are being reinvested whenever "
                r'<span class="math inline">\(t\in B\)</span>'
                ", hence preventing the negative prices. Dividends "
                r'<span class="math inline">\(d_{i,t}\)</span>'
                " are already embedded in "
                r'<span class="math inline">\(K_t\)</span>'
                ", so there is no need for the strategy to know about them.</p>"
            )
        if text.startswith("The interested reader will find many practical ways"):
            return (
                "<p>The interested reader will find many practical ways of computing hedging weights in López de Prado and Leinweber [2012] and Bailey and López de Prado [2012]. "
                "For the sake of completeness, let us review one way to derive the vector "
                r'<span class="math inline">\(\{\omega_t\}\)</span>'
                " used in the previous section. Consider an IID multivariate Gaussian process characterized by a vector of means "
                r'<span class="math inline">\(\mu\)</span>'
                ", of size "
                r'<span class="math inline">\(N\times1\)</span>'
                ", and a covariance matrix "
                r'<span class="math inline">\(V\)</span>'
                ", of size "
                r'<span class="math inline">\(N\times N\)</span>'
                ". This stochastic process describes an invariant random variable, like the returns of stocks, the changes in yield of bonds, or changes in options' volatilities, for a portfolio of "
                r'<span class="math inline">\(N\)</span>'
                " instruments. We would like to compute the vector of allocations "
                r'<span class="math inline">\(\omega\)</span>'
                " that conforms to a particular distribution of risks across "
                r'<span class="math inline">\(V\)</span>'
                "'s principal components. First, we perform a spectral decomposition, "
                r'<span class="math inline">\(VW=W\Lambda\)</span>'
                ", where the columns in "
                r'<span class="math inline">\(W\)</span>'
                " are reordered so that the elements of "
                r'<span class="math inline">\(\Lambda\)</span>'
                "'s diagonal are sorted in descending order. Second, given a vector of allocations "
                r'<span class="math inline">\(\omega\)</span>'
                ", we can compute the portfolio's risk as</p>"
            )
        if text.startswith("𝜔 on the orthogonal basis"):
            return (
                "<p>where "
                r'<span class="math inline">\(\beta\)</span>'
                " represents the projection of "
                r'<span class="math inline">\(\omega\)</span>'
                " on the orthogonal basis. Third, "
                r'<span class="math inline">\(\Lambda\)</span>'
                " is a diagonal matrix, thus "
                r'<span class="math inline">\(\sigma^2=\sum_{n=1}^{N}\beta_n^2\Lambda_{n,n}\)</span>'
                ".</p>"
            )
        if text.startswith("and the risk attributed to the nth component is Rn"):
            return "<p>The risk attributed to the nth component is</p>"
        if text.startswith("with R′ 1N = 1"):
            return (
                "<p>with "
                r'<span class="math inline">\(R^\prime \mathbf{1}_N=1\)</span>'
                ", and "
                r'<span class="math inline">\(1_N\)</span>'
                " is a vector of "
                r'<span class="math inline">\(N\)</span>'
                " ones. You can interpret "
                r'<span class="math inline">\(\{R_n\}_{n=1,\ldots,N}\)</span>'
                " as the distribution of risks across the orthogonal components. Fourth, we would like to compute the vector "
                r'<span class="math inline">\(\omega\)</span>'
                " that delivers a user-defined risk distribution "
                r'<span class="math inline">\(R\)</span>'
                ". From earlier steps, "
                r'<span class="math inline">\(\beta=\{\sigma\sqrt{R_n/\Lambda_{n,n}}\}_{n=1,\ldots,N}\)</span>'
                ", which represents the allocation in the new (orthogonal) basis. Fifth, the allocation in the old basis is given by "
                r'<span class="math inline">\(\omega=W\beta\)</span>'
                ". Re-scaling "
                r'<span class="math inline">\(\omega\)</span>'
                " merely re-scales "
                r'<span class="math inline">\(\sigma\)</span>'
                ", hence keeping the risk distribution constant. Figure 2.2 illustrates the contribution to risk per principal component for an</p>"
            )
        if text.startswith("with boundary condition S0 = 0. This procedure"):
            return (
                "<p>with boundary condition "
                r'<span class="math inline">\(S_0=0\)</span>'
                ". This procedure would recommend an action at the first "
                r'<span class="math inline">\(t\)</span>'
                " satisfying "
                r'<span class="math inline">\(S_t\ge h\)</span>'
                ", for some threshold "
                r'<span class="math inline">\(h\)</span>'
                " (the filter size). Note that "
                r'<span class="math inline">\(S_t=0\)</span>'
                " whenever "
                r'<span class="math inline">\(y_t\le \mathbb{E}_{t-1}[y_t]-S_{t-1}\)</span>'
                ". This zero floor means that we will skip some downward deviations that otherwise would make "
                r'<span class="math inline">\(S_t\)</span>'
                " negative. The reason is, the filter is set up to identify a sequence of upside divergences from any reset level zero. "
                "In particular, the threshold is activated when</p>"
            )
        return f"<p>{mathify_chapter_02_text(text)}</p>"
    return f"<p>{mathify_general_text(text)}</p>"


def chapter_list_html(chapter: Chapter, block: Block) -> str | None:
    if chapter.slug == "chapter-14":
        override = chapter_14_list_html(block)
        if override is not None:
            return override
    if chapter.slug == "chapter-13":
        override = chapter_13_list_html(block)
        if override is not None:
            return override
    if chapter.slug == "chapter-12":
        if block.kind == "olist" and block.lines:
            first = block.lines[0]
            if first.startswith("The performance we will obtain for 2008"):
                return ""
            if first.startswith("Partition T observations"):
                return chapter_12_algorithm_list_html()
            tag = "ol"
            items = "".join(
                f"<li>{style_citations_html(chapter_12_text_html(join_paragraph_lines([item])))}</li>"
                for item in block.lines
            )
            return f"<{tag}>{items}</{tag}>"
    if chapter.slug == "chapter-11":
        if block.kind == "olist" and block.lines and block.lines[0].startswith("Form the training set J"):
            return ""
        if block.kind in {"ulist", "olist"}:
            tag = "ol" if block.kind == "olist" else "ul"
            items = "".join(
                f"<li>{style_citations_html(chapter_11_text_html(join_paragraph_lines([item])))}</li>"
                for item in block.lines
            )
            return f"<{tag}>{items}</{tag}>"
    if chapter.slug == "chapter-10":
        if block.kind == "ulist" and block.lines and block.lines[0].startswith("m̃"):
            return (
                "<ul>"
                "<li>"
                + math_inline(r"\tilde m[\omega,-1]=-1")
                + ", "
                + math_inline(r"\tilde m[\omega,1]=1")
                + ".</li>"
                "<li>Curvature can be directly manipulated through "
                + math_inline(r"\omega")
                + ".</li>"
                "<li>For "
                + math_inline(r"\omega>1")
                + ", the function goes from concave to convex, rather than the other way around, hence the function is almost flat around the inflection point.</li>"
                "</ul>"
            )
    if chapter.slug == "chapter-09":
        if block.kind == "ulist" and block.lines and block.lines[0].startswith("pn,k"):
            return (
                "<ul>"
                "<li>"
                + math_inline(r"p_{n,k}")
                + " is the probability associated with prediction "
                + math_inline("n")
                + " of label "
                + math_inline("k")
                + ".</li>"
                "<li>"
                + math_inline("Y")
                + " is a 1-of-"
                + math_inline("K")
                + " binary indicator matrix, such that "
                + math_inline(r"y_{n,k}=1")
                + " when observation "
                + math_inline("n")
                + " was assigned label "
                + math_inline("k")
                + " out of "
                + math_inline("K")
                + " possible labels, and 0 otherwise.</li>"
                "</ul>"
            )
    if chapter.slug == "chapter-01":
        if block.kind == "olist" and block.lines and block.lines[0].startswith("Instead, backtest"):
            return ""
        if block.kind == "olist" and block.lines and block.lines[0].startswith("Embargo:"):
            return (
                "<ol>"
                "<li><strong>Embargo:</strong> Initially, the strategy is run on data observed after the end date of the backtest. Such a period may have been reserved by the backtesters, or it may be the result of implementation delays. If embargoed performance is consistent with backtest results, the strategy is promoted to the next stage.</li>"
                "<li><strong>Paper trading:</strong> At this point, the strategy is run on a live, real-time feed. In this way, performance will account for data parsing latencies, calculation latencies, execution delays, and other time lapses between observation and positioning. Paper trading will take place for as long as it is needed to gather enough evidence that the strategy performs as expected.</li>"
                "<li><strong>Graduation:</strong> At this stage, the strategy manages a real position, whether in isolation or as part of an ensemble. Performance is evaluated precisely, including attributed risk, returns, and costs.</li>"
                "<li><strong>Re-allocation:</strong> Based on the production performance, the allocation to graduated strategies is re-assessed frequently and automatically in the context of a diversified portfolio. In general, a strategy's allocation follows a concave function. The initial allocation (at graduation) is small. As time passes, and the strategy performs as expected, the allocation is increased. Over time, performance decays, and allocations become gradually smaller.</li>"
                "<li><strong>Decommission:</strong> Eventually, all strategies are discontinued. This happens when they perform below expectations for a sufficiently extended period of time to conclude that the supporting theory is no longer backed by empirical evidence.</li>"
                "</ol>"
            )
        if block.kind == "olist" and block.lines and block.lines[0].startswith("Re-allocation:"):
            return ""
        if block.kind == "ulist" and block.lines:
            first = block.lines[0]
            if first.startswith("Problem: Garbage"):
                return chapter_01_strategy_list("data")
            if first.startswith("Problem: A specialized"):
                return chapter_01_strategy_list("software-problem")
            if first.startswith("How:") and len(block.lines) > 1 and block.lines[1].startswith("Chapters 2–22"):
                return chapter_01_strategy_list("software-how")
            if first.startswith("Problem: ML involves"):
                return chapter_01_strategy_list("hardware")
            if first.startswith("Problem: Mathematical proofs"):
                return chapter_01_strategy_list("math")
            if first.startswith("Solution: Use experimental math") or (first.startswith("How:") and len(block.lines) > 1 and block.lines[1].startswith("Chapter 5:")):
                return ""
            if first.startswith("Problem: Amateurs"):
                return chapter_01_strategy_list("meta")
            if first.startswith("Problem: Standard cross-validation"):
                return chapter_01_strategy_list("overfitting")
            if first.startswith("Overfitting is unethical"):
                return ""
    if chapter.slug == "chapter-03":
        if not block.lines:
            return None
        first = block.lines[0]
        if (
            block.kind == "ulist"
            and first.startswith("close: A pandas series of prices.")
            and any(line.startswith("events: A pandas dataframe") for line in block.lines)
        ):
            return (
                "<ul>"
                "<li><code>close</code>: A pandas series of prices.</li>"
                "<li><code>events</code>: A pandas dataframe, with columns:"
                "<ul>"
                "<li><code>t1</code>: The timestamp of the vertical barrier. When the value is <code>np.nan</code>, there will not be a vertical barrier.</li>"
                "<li><code>trgt</code>: The unit width of the horizontal barriers.</li>"
                "</ul></li>"
                "<li><code>ptSl</code>: A list of two non-negative float values:"
                "<ul>"
                "<li><code>ptSl[0]</code>: The factor that multiplies <code>trgt</code> to set the width of the upper barrier. If 0, there will not be an upper barrier.</li>"
                "<li><code>ptSl[1]</code>: The factor that multiplies <code>trgt</code> to set the width of the lower barrier. If 0, there will not be a lower barrier.</li>"
                "</ul></li>"
                "<li><code>molecule</code>: A list with the subset of event indices that will be processed by a single thread. Its use will become clear later on in the chapter.</li>"
                "</ul>"
            )
        if block.kind == "ulist" and first.startswith("Three useful configurations:"):
            return (
                "<ul>"
                "<li><strong>Three useful configurations:</strong>"
                "<ul>"
                "<li><code>[1,1,1]</code>: This is the standard setup, where we define three barrier exit conditions. We would like to realize a profit, but we have a maximum tolerance for losses and a holding period.</li>"
                "<li><code>[0,1,1]</code>: In this setup, we would like to exit after a number of bars, unless we are stopped-out.</li>"
                "<li><code>[1,1,0]</code>: Here we would like to take a profit as long as we are not stopped-out. This is somewhat unrealistic in that we are willing to hold the position for as long as it takes.</li>"
                "</ul></li>"
                "<li><strong>Three less realistic configurations:</strong>"
                "<ul>"
                "<li><code>[0,0,1]</code>: This is equivalent to the fixed-time horizon method. It may still be useful when applied to volume-, dollar-, or information-driven bars, and multiple forecasts are updated within the horizon.</li>"
                "<li><code>[1,0,1]</code>: A position is held until a profit is made or the maximum holding period is exceeded, without regard for the intermediate unrealized losses.</li>"
                "<li><code>[1,0,0]</code>: A position is held until a profit is made. It could mean being locked on a losing position for years.</li>"
                "</ul></li>"
                "<li><strong>Two illogical configurations:</strong>"
                "<ul>"
                "<li><code>[0,1,0]</code>: This is an aimless configuration, where we hold a position until we are stopped-out.</li>"
                "<li><code>[0,0,0]</code>: There are no barriers. The position is locked forever, and no label is generated.</li>"
                "</ul></li>"
                "</ul>"
            )
        if block.kind == "ulist" and first.startswith("ret: The return realized"):
            return (
                "<ul>"
                "<li><code>ret</code>: The return realized at the time of the first touched barrier.</li>"
                "<li><code>bin</code>: The label, "
                + math_inline(r"\{-1,0,1\}")
                + ", as a function of the sign of the outcome. The function can be easily adjusted to label as "
                + math_inline("0")
                + " those events when the vertical barrier was touched first, which we leave as an exercise.</li>"
                "</ul>"
            )
        if block.kind == "olist" and first.startswith("Use your forecasts from the primary model"):
            return (
                "<ol>"
                "<li>Use your forecasts from the primary model, and generate meta-labels. Remember, horizontal barriers do not need to be symmetric in this case.</li>"
                "<li>Fit your model again on the same training set, but this time using the meta-labels you just generated.</li>"
                "<li>Combine the “sides” from the first ML model with the “sizes” from the second ML model.</li>"
                "</ol>"
            )
        if block.kind in {"ulist", "olist"}:
            tag = "ol" if block.kind == "olist" else "ul"
            items = "".join(f"<li>{chapter_03_text_html(join_paragraph_lines([item]))}</li>" for item in block.lines)
            return f"<{tag}>{items}</{tag}>"
    if chapter.slug == "chapter-04":
        if not block.lines:
            return None
        first = block.lines[0]
        if block.kind == "olist" and first.startswith("d = a + b"):
            return (
                "<ol>"
                "<li>"
                + math_inline(r"d=a+b\sum_{i=1}^{I}\bar u_i=1\Rightarrow a=1-b\sum_{i=1}^{I}\bar u_i")
                + ".</li>"
                "<li>Contingent on "
                + math_inline("c")
                + ":"
                "<ol type=\"a\">"
                "<li>"
                + math_inline(r"d=a+b0=c\Rightarrow b=(1-c)\left(\sum_{i=1}^{I}\bar u_i\right)^{-1},\ \forall c\in[0,1]")
                + ".</li>"
                "<li>"
                + math_inline(r"d=a-bc\sum_{i=1}^{I}\bar u_i=0\Rightarrow b=(c+1)\left(\sum_{i=1}^{I}\bar u_i\right)^{-1},\ \forall c\in(-1,0)")
                + ".</li>"
                "</ol></li>"
                "</ol>"
            )
        if block.kind == "ulist" and first.startswith("c = 1 means"):
            return (
                "<ul>"
                "<li>"
                + math_inline("c=1")
                + " means that there is no time decay.</li>"
                "<li>"
                + math_inline("0<c<1")
                + " means that weights decay linearly over time, but every observation still receives a strictly positive weight, regardless of how old.</li>"
                "</ul>"
            )
        if block.kind == "ulist" and first.startswith("c = 0 means"):
            return (
                "<ul>"
                "<li>"
                + math_inline("c=0")
                + " means that weights converge linearly to zero, as they become older.</li>"
                "<li>"
                + math_inline("c<0")
                + " means that the oldest portion "
                + math_inline("cT")
                + " of the observations receive zero weight (i.e., they are erased from memory).</li>"
                "</ul>"
            )
        if block.kind in {"ulist", "olist"}:
            tag = "ol" if block.kind == "olist" else "ul"
            items = "".join(f"<li>{chapter_04_text_html(join_paragraph_lines([item]))}</li>" for item in block.lines)
            return f"<{tag}>{items}</{tag}>"
    if chapter.slug == "chapter-06":
        if not block.lines:
            return None
        first = block.lines[0]
        if block.kind == "olist" and first.startswith("Bias:"):
            return (
                "<ol>"
                "<li><strong>Bias:</strong> This error is caused by unrealistic assumptions. When bias is high, the ML algorithm has failed to recognize important relations between features and outcomes. In this situation, the algorithm is said to be “underfit.”</li>"
                "<li><strong>Variance:</strong> This error is caused by sensitivity to small changes in the training set. When variance is high, the algorithm has overfit the training set, and that is why even minimal changes in the training set can produce wildly different predictions. Rather than modelling the general patterns in the training set, the algorithm has mistaken noise with signal.</li>"
                "<li><strong>Noise:</strong> This error is caused by the variance of the observed values, like unpredictable changes or measurement errors. This is the irreducible error, which cannot be explained by any model.</li>"
                "</ol>"
            )
        if block.kind == "olist" and first.startswith("Noise:"):
            return ""
        if block.kind == "olist" and first.startswith("Set a parameter max_features"):
            return (
                "<ol>"
                "<li>Set the parameter "
                + chapter_06_code("max_features")
                + " to a lower value, as a way of forcing discrepancy between trees.</li>"
                "<li><strong>Early stopping:</strong> Set the regularization parameter "
                + chapter_06_code("min_weight_fraction_leaf")
                + " to a sufficiently large value, e.g. 5%, such that out-of-bag accuracy converges to out-of-sample, k-fold accuracy.</li>"
                "<li>Use "
                + chapter_06_code("BaggingClassifier")
                + " on "
                + chapter_06_code("DecisionTreeClassifier")
                + " where "
                + chapter_06_code("max_samples")
                + " is set to the average uniqueness ("
                + chapter_06_code("avgU")
                + ") between samples."
                "<ol type=\"a\">"
                "<li>"
                + chapter_06_code("clf=DecisionTreeClassifier(criterion='entropy',max_features='auto',class_weight='balanced')")
                + "</li>"
                "<li>"
                + chapter_06_code("bc=BaggingClassifier(base_estimator=clf,n_estimators=1000,max_samples=avgU,max_features=1.)")
                + "</li>"
                "</ol></li>"
                "<li>Use "
                + chapter_06_code("BaggingClassifier")
                + " on "
                + chapter_06_code("RandomForestClassifier")
                + " where "
                + chapter_06_code("max_samples")
                + " is set to the average uniqueness ("
                + chapter_06_code("avgU")
                + ") between samples."
                "<ol type=\"a\">"
                "<li>"
                + chapter_06_code("clf=RandomForestClassifier(n_estimators=1,criterion='entropy',bootstrap=False,class_weight='balanced_subsample')")
                + "</li>"
                "<li>"
                + chapter_06_code("bc=BaggingClassifier(base_estimator=clf,n_estimators=1000,max_samples=avgU,max_features=1.)")
                + "</li>"
                "</ol></li>"
                "<li>Modify the RF class to replace standard bootstrapping with sequential bootstrapping.</li>"
                "</ol>"
            )
        if block.kind == "olist" and first.startswith("Modify the RF class"):
            return ""
        if block.kind == "ulist" and first.startswith("Individual classifiers are fit sequentially"):
            return (
                "<ul>"
                "<li>Individual classifiers are fit sequentially.</li>"
                "<li>Poor-performing classifiers are dismissed.</li>"
                "<li>Observations are weighted differently in each iteration.</li>"
                "<li>The ensemble forecast is a weighted average of the individual learners.</li>"
                "</ul>"
            )
        if block.kind == "ulist" and first.startswith("Observations are weighted differently"):
            return ""
    if chapter.slug == "chapter-07":
        if not block.lines:
            return None
        first = block.lines[0]
        if block.kind == "olist" and first.startswith("The dataset is partitioned"):
            return (
                "<ol>"
                "<li>The dataset is partitioned into "
                + math_inline("k")
                + " subsets.</li>"
                "<li>For "
                + math_inline(r"i=1,\ldots,k")
                + ":"
                "<ol type=\"a\">"
                "<li>The ML algorithm is trained on all subsets excluding "
                + math_inline("i")
                + ".</li>"
                "<li>The fitted ML algorithm is tested on "
                + math_inline("i")
                + ".</li>"
                "</ol></li>"
                "</ol>"
            )
        if block.kind == "ulist" and first.startswith("Because of the serial correlation"):
            return (
                "<ul>"
                "<li>Because of the serial correlation, "
                + math_inline(r"X_t\approx X_{t+1}")
                + ".</li>"
                "<li>Because labels are derived from overlapping datapoints, "
                + math_inline(r"Y_t\approx Y_{t+1}")
                + ".</li>"
                "</ul>"
            )
        if block.kind == "olist" and first.startswith("Drop from the training set"):
            return (
                "<ol>"
                "<li>Drop from the training set any observation "
                + math_inline("i")
                + " where "
                + math_inline("Y_i")
                + " is a function of information used to determine "
                + math_inline("Y_j")
                + ", and "
                + math_inline("j")
                + " belongs to the testing set."
                "<ol type=\"a\"><li>For example, "
                + math_inline("Y_i")
                + " and "
                + math_inline("Y_j")
                + " should not span overlapping periods (see Chapter 4 for a discussion of sample uniqueness).</li></ol>"
                "</li>"
                "<li>Avoid overfitting the classifier. In this way, even if some leakage occurs, the classifier will not be able to profit from it. Use:"
                "<ol type=\"a\">"
                "<li>Early stopping of the base estimators (see Chapter 6).</li>"
                "<li>Bagging of classifiers, while controlling for oversampling on redundant examples, so that the individual classifiers are as diverse as possible."
                "<ol type=\"i\">"
                "<li>Set "
                + chapter_07_code("max_samples")
                + " to the average uniqueness.</li>"
                "<li>Apply sequential bootstrap (Chapter 4).</li>"
                "</ol></li>"
                "</ol></li>"
                "</ol>"
            )
        if block.kind == "olist" and first.startswith("tj,0"):
            return (
                "<ol>"
                "<li>"
                + math_inline(r"t_{j,0}\le t_{i,0}\le t_{j,1}")
                + "</li>"
                "<li>"
                + math_inline(r"t_{j,0}\le t_{i,1}\le t_{j,1}")
                + "</li>"
                "<li>"
                + math_inline(r"t_{i,0}\le t_{j,0}\le t_{j,1}\le t_{i,1}")
                + "</li>"
                "</ol>"
            )
        if block.kind == "olist" and first.startswith("Scoring functions do not know"):
            return (
                "<ol>"
                "<li>Scoring functions do not know "
                + chapter_07_code("classes_")
                + ", as a consequence of sklearn's reliance on "
                + chapter_07_code("numpy")
                + " arrays rather than "
                + chapter_07_code("pandas")
                + " series: <a href=\"https://github.com/scikit-learn/scikit-learn/issues/6231\">https://github.com/scikit-learn/scikit-learn/issues/6231</a></li>"
                "<li>"
                + chapter_07_code("cross_val_score")
                + " will give different results because it passes weights to the "
                + chapter_07_code("fit")
                + " method, but not to the "
                + chapter_07_code("log_loss")
                + " method: <a href=\"https://github.com/scikit-learn/scikit-learn/issues/9144\">https://github.com/scikit-learn/scikit-learn/issues/9144</a></li>"
                "</ol>"
            )
    if chapter.slug == "chapter-08":
        if not block.lines:
            return None
        first = block.lines[0]
        if block.kind == "olist" and first.startswith("Masking effects"):
            return (
                "<ol>"
                "<li>Masking effects take place when some features are systematically ignored by tree-based classifiers in favor of others. In order to avoid them, set <code>max_features=int(1)</code> when using sklearn's RF class. In this way, only one random feature is considered per level."
                "<ol type=\"a\">"
                "<li>Every feature is given a chance (at some random levels of some random trees) to reduce impurity.</li>"
                "<li>Make sure that features with zero importance are not averaged, since the only reason for a 0 is that the feature was not randomly chosen. Replace those values with <code>np.nan</code>.</li>"
                "</ol></li>"
                "<li>The procedure is obviously IS. Every feature will have some importance, even if they have no predictive power whatsoever.</li>"
                "<li>MDI cannot be generalized to other non-tree based classifiers.</li>"
                "<li>By construction, MDI has the nice property that feature importances add up to 1, and every feature importance is bounded between 0 and 1.</li>"
                "<li>The method does not address substitution effects in the presence of correlated features. MDI dilutes the importance of substitute features, because of their interchangeability: The importance of two identical features will be halved, as they are randomly chosen with equal probability.</li>"
                "<li>Strobl et al. [2007] show experimentally that MDI is biased towards some predictor variables. White and Liu [1994] argue that, in case of single decision trees, this bias is due to an unfair advantage given by popular impurity functions toward predictors with a large number of categories.</li>"
                "</ol>"
            )
        if block.kind == "olist" and first.startswith("This method can be applied to any classifier") and len(block.lines) >= 5:
            return (
                "<ol>"
                "<li>This method can be applied to any classifier, not only tree-based classifiers.</li>"
                "<li>MDA is not limited to accuracy as the sole performance score. For example, in the context of meta-labeling applications, we may prefer to score a classifier with F1 rather than accuracy (see Chapter 14, Section 14.8 for an explanation). That is one reason a better descriptive name would have been “permutation importance.” When the scoring function does not correspond to a metric space, MDA results should be used as a ranking.</li>"
                "<li>Like MDI, the procedure is also susceptible to substitution effects in the presence of correlated features. Given two identical features, MDA always considers one to be redundant to the other. Unfortunately, MDA will make both features appear to be outright irrelevant, even if they are critical.</li>"
                "<li>Unlike MDI, it is possible that MDA concludes that all features are unimportant. That is because MDA is based on OOS performance.</li>"
                "<li>The CV must be purged and embargoed, for the reasons explained in Chapter 7.</li>"
                "</ol>"
            )
        if block.kind == "olist" and first.startswith("This method can be applied to any classifier, not only tree-based classifiers.") and len(block.lines) == 4:
            return (
                "<ol>"
                "<li>This method can be applied to any classifier, not only tree-based classifiers.</li>"
                "<li>SFI is not limited to accuracy as the sole performance score.</li>"
                "<li>Unlike MDI and MDA, no substitution effects take place, since only one feature is taken into consideration at a time.</li>"
                "<li>Like MDA, it can conclude that all features are unimportant, because performance is evaluated via OOS CV.</li>"
                "</ol>"
            )
        if block.kind == "olist" and first.startswith("Informative:"):
            return (
                "<ol>"
                "<li><strong>Informative:</strong> These are features that are used to determine the label.</li>"
                "<li><strong>Redundant:</strong> These are random linear combinations of the informative features. They will cause substitution effects.</li>"
                "<li><strong>Noise:</strong> These are features that have no bearing on determining the observation's label.</li>"
                "</ol>"
            )
    if chapter.slug == "chapter-21":
        if block.kind == "ulist" and block.lines and block.lines[0].startswith("= diag"):
            return math_display(r"r=\operatorname{diag}[\mu^\prime\omega]-\tau[\omega]")
        if block.kind == "ulist" and block.lines and block.lines[0].startswith("𝜏1 [𝜔]"):
            return (
                math_display(
                    r"\begin{aligned}"
                    r"\tau_1[\omega]&=\sum_{n=1}^{N}c_{n,1}\sqrt{|\omega_{n,1}-\omega_n^*|},\\"
                    r"\tau_h[\omega]&=\sum_{n=1}^{N}c_{n,h}\sqrt{|\omega_{n,h}-\omega_{n,h-1}|},\quad h=2,\ldots,H."
                    r"\end{aligned}"
                )
                + "<p>"
                + math_inline(r"\omega_n^*")
                + " is the initial allocation to instrument "
                + math_inline("n")
                + ", "
                + math_inline(r"n=1,\ldots,N")
                + ". The implementation below defaults to "
                + math_inline(r"\omega^*=0")
                + " unless an optional initial allocation <code>w0</code> is supplied.</p>"
            )
    if chapter.slug == "chapter-20":
        if block.kind == "ulist" and block.lines and block.lines[0].startswith("func: A callback"):
            return (
                "<ul>"
                "<li><code>func</code>: A callback function, which will be executed in parallel</li>"
                "<li><code>pdObj</code>: A tuple containing:"
                "<ul>"
                "<li>The name of the argument used to pass molecules to the callback function</li>"
                "<li>A list of indivisible tasks (atoms), which will be grouped into molecules</li>"
                "</ul></li>"
                "<li><code>numThreads</code>: The number of threads that will be used in parallel (one processor per thread)</li>"
                "<li><code>mpBatches</code>: Number of parallel batches (jobs per core)</li>"
                "<li><code>linMols</code>: Whether partitions will be linear or double-nested</li>"
                "<li><code>kargs</code>: Keyword arguments needed by <code>func</code></li>"
                "</ul>"
            )
    if chapter.slug == "chapter-18":
        if block.kind == "ulist" and block.lines and block.lines[0].startswith("In R:"):
            return (
                "<ul>"
                '<li>In R: <a href="http://cran.r-project.org/web/packages/entropy/entropy.pdf">http://cran.r-project.org/web/packages/entropy/entropy.pdf</a></li>'
                '<li>In Python: <a href="https://code.google.com/archive/p/pyentropy/">https://code.google.com/archive/p/pyentropy/</a></li>'
                "</ul>"
            )
        if block.kind == "ulist" and block.lines and block.lines[0].startswith("The value n is constant"):
            return (
                "<ul>"
                "<li>The value "
                + math_inline("n")
                + " is constant for a sliding window, and "
                + math_inline("n=i")
                + " for an expanding window.</li>"
                "<li>Computing "
                + math_inline(r"L_i^n")
                + " requires data "
                + math_inline(r"x_{i-n}^{i+n-1}")
                + ". In other words, index "
                + math_inline("i")
                + " must be at the center of the window. This is important in order to guarantee that both matching strings are of the same length. If they are not of the same length, "
                + math_inline("l")
                + " will have a limited range and its maximum will be underestimated.</li>"
                "<li>Some overlap between the two substrings is allowed, although obviously both cannot start at "
                + math_inline("i")
                + ".</li>"
                "</ul>"
            )
        if block.kind == "ulist" and block.lines and block.lines[0].startswith("Some overlap"):
            return ""
        if block.kind == "olist" and block.lines and block.lines[0].startswith("The generalized weighted mean"):
            return "<p>The generalized weighted mean of " + math_inline("x") + " with weights " + math_inline("p") + " on a power " + math_inline(r"q\ne0") + " is defined as</p>"
        if block.kind == "ulist" and block.lines and block.lines[0].startswith("Minimum:"):
            return (
                "<ul>"
                "<li><strong>Minimum:</strong>"
                + math_display(r"\lim_{q\to-\infty}M_q[x,p]=\min_i\{x_i\}")
                + "</li>"
                "<li><strong>Harmonic mean:</strong>"
                + math_display(r"M_{-1}[x,p]=\left(\sum_{i=1}^{n}p_i x_i^{-1}\right)^{-1}")
                + "</li>"
                "<li><strong>Geometric mean:</strong>"
                + math_display(r"\lim_{q\to0}M_q[x,p]=e^{\sum_{i=1}^{n}p_i\log[x_i]}=\prod_{i=1}^{n}x_i^{p_i}")
                + "</li>"
                "<li><strong>Arithmetic mean:</strong>"
                + math_display(r"M_1[x,\{n^{-1}\}_{i=1,\ldots,n}]=n^{-1}\sum_{i=1}^{n}x_i")
                + "</li>"
                "</ul>"
            )
        if block.kind == "ulist" and block.lines and block.lines[0].startswith("Weighted mean:"):
            return (
                "<ul>"
                "<li><strong>Weighted mean:</strong>"
                + math_display(r"M_1[x,p]=\sum_{i=1}^{n}p_i x_i")
                + "</li>"
                "<li><strong>Quadratic mean:</strong>"
                + math_display(r"M_2[x,p]=\left(\sum_{i=1}^{n}p_i x_i^2\right)^{1/2}")
                + "</li>"
                "<li><strong>Maximum:</strong>"
                + math_display(r"\lim_{q\to+\infty}M_q[x,p]=\max_i\{x_i\}")
                + "</li>"
                "</ul>"
            )
    if chapter.slug == "chapter-17":
        if block.kind == "ulist" and block.lines and block.lines[0].startswith("CUSUM tests:"):
            return (
                "<ul>"
                "<li><strong>CUSUM tests:</strong> These test whether the cumulative forecasting errors significantly deviate from white noise.</li>"
                "<li><strong>Explosiveness tests:</strong> Beyond deviation from white noise, these test whether the process exhibits exponential growth or collapse, as this is inconsistent with a random walk or stationary process, and it is unsustainable in the long run."
                "<ul>"
                "<li><strong>Right-tail unit-root tests:</strong> These tests evaluate the presence of exponential growth or collapse, while assuming an autoregressive specification.</li>"
                "<li><strong>Sub/super-martingale tests:</strong> These tests evaluate the presence of exponential growth or collapse under a variety of functional forms.</li>"
                "</ul></li>"
                "</ul>"
            )
        if block.kind == "ulist" and block.lines and block.lines[0].startswith("Right-tail unit-root tests:"):
            return ""
        if block.kind == "ulist" and block.lines and block.lines[0].startswith("Steady:"):
            return (
                "<ul>"
                "<li><strong>Steady:</strong> "
                + math_inline(r"-2<\beta<0\Rightarrow\lim_{t\to\infty}\mathbb{E}[\log[y_t]]=-\frac{\alpha}{\beta}")
                + "."
                "<ul>"
                "<li>The disequilibrium is "
                + math_inline(r"\log[y_t]-\left(-\frac{\alpha}{\beta}\right)=\log[\tilde y_t]")
                + ".</li>"
                "<li>For "
                + math_inline(r"-1<\beta<0")
                + ", "
                + math_inline(r"\frac{\mathbb{E}[\log[\tilde y_t]]}{\log[\tilde y_0]}=(1+\beta)^t=\frac{1}{2}")
                + " at "
                + math_inline(r"t=-\frac{\log[2]}{\log[1+\beta]}")
                + " (half-life).</li>"
                "</ul></li>"
                "<li><strong>Unit-root:</strong> "
                + math_inline(r"\beta=0")
                + ", where the system is non-stationary, and behaves as a martingale.</li>"
                "<li><strong>Explosive:</strong> "
                + math_inline(r"\beta>0")
                + ", where"
                + math_display(r"\lim_{t\to\infty}\mathbb{E}[\log[y_t]]=\begin{cases}-\infty,&\log[y_0]<-\frac{\alpha}{\beta},\\+\infty,&\log[y_0]>-\frac{\alpha}{\beta}.\end{cases}")
                + "</li>"
                "</ul>"
            )
        if block.kind == "ulist" and block.lines and block.lines[0].startswith("Explosive:"):
            return ""
        if block.kind == "ulist" and block.lines and block.lines[0].startswith("logP:"):
            return (
                "<ul>"
                "<li><code>logP</code>: a pandas series containing log-prices</li>"
                "<li><code>minSL</code>: the minimum sample length ("
                + math_inline(r"\tau")
                + "), used by the final regression</li>"
                "<li><code>constant</code>: the deterministic terms in the regression"
                "<ul>"
                "<li><code>'nc'</code>: no constant and no time trend</li>"
                "<li><code>'c'</code>: constant only</li>"
                "<li><code>'ct'</code>: a constant plus a linear time trend</li>"
                "<li><code>'ctt'</code>: a constant plus a second-degree polynomial time trend</li>"
                "</ul></li>"
                "<li><code>lags</code>: the number of lags used in the ADF specification</li>"
                "</ul>"
            )
        if block.kind == "ulist" and block.lines and block.lines[0].startswith("Polynomial trend (SM-Poly"):
            label = html.escape(block.lines[0])
            return f"<p><strong>{label}</strong></p>"
        if block.kind == "ulist" and block.lines and block.lines[0].startswith(("Exponential trend", "Power trend")):
            label = html.escape(block.lines[0])
            return f"<p><strong>{label}</strong></p>"
    if chapter.slug == "chapter-19":
        if block.kind == "olist" and block.lines and block.lines[0].startswith("A number of studies"):
            return ""
        if block.kind == "ulist" and block.lines and block.lines[0].startswith("A noise trader"):
            return (
                "<ul>"
                "<li>A noise trader who trades a quantity "
                + math_inline(r"u\sim N[0,\sigma_u^2]")
                + ", independent of "
                + math_inline("v")
                + ".</li>"
                "<li>An informed trader who knows "
                + math_inline("v")
                + " and demands a quantity "
                + math_inline("x")
                + ", through a market order.</li>"
                "</ul>"
            )
        if block.kind == "ulist" and block.lines and block.lines[0].startswith("Quote stuffers:"):
            return (
                "<ul>"
                "<li><strong>Quote stuffers:</strong> They engage in “latency arbitrage.” Their strategy involves overwhelming an exchange with messages, with the sole intention of slowing down competing algorithms, which are forced to parse messages that only the originators know can be ignored.</li>"
                "<li><strong>Quote danglers:</strong> This strategy sends quotes that force a squeezed trader to chase a price against her interests. O’Hara [2011] presents evidence of their disruptive activities.</li>"
                "<li><strong>Liquidity squeezers:</strong> When a distressed large investor is forced to unwind her position, predatory algorithms trade in the same direction, draining as much liquidity as possible. As a result, prices overshoot and they make a profit (Carlin et al. [2007]).</li>"
                "<li><strong>Pack hunters:</strong> Predators hunting independently become aware of one another's activities, and form a pack in order to maximize the chances of triggering a cascading effect (Donefer [2010], Fabozzi et al. [2011], Jarrow and Protter [2011]). NANEX [2011] shows what appears to be pack hunters forcing a stop loss. Although their individual actions are too small to raise the regulator's suspicion, their collective action may be market-manipulative. When that is the case, it is very hard to prove their collusion, since they coordinate in a decentralized, spontaneous manner.</li>"
                "</ul>"
            )
        if block.kind == "ulist" and block.lines and block.lines[0].startswith(("Quote danglers:", "Liquidity squeezers:", "Pack hunters:")):
            return ""
    if chapter.slug == "chapter-16":
        if block.kind == "olist" and block.lines and block.lines[0].startswith("The algorithm is initialized"):
            return (
                "<ol class=\"algorithm-list\">"
                "<li>The algorithm is initialized by:"
                "<ol type=\"a\">"
                "<li>Setting the list of items: "
                + math_inline(r"L=\{L_0\}")
                + ", with "
                + math_inline(r"L_0=\{n\}_{n=1,\ldots,N}")
                + ".</li>"
                "<li>Assigning a unit weight to all items: "
                + math_inline(r"w_n=1,\ \forall n=1,\ldots,N")
                + ".</li>"
                "</ol></li>"
                "<li>If "
                + math_inline(r"|L_i|=1,\ \forall L_i\in L")
                + ", then stop.</li>"
                "<li>For each "
                + math_inline(r"L_i\in L")
                + " such that "
                + math_inline(r"|L_i|>1")
                + ":"
                "<ol type=\"a\">"
                "<li>Bisect "
                + math_inline(r"L_i")
                + " into two subsets, "
                + math_inline(r"L_i^{(1)}\cup L_i^{(2)}=L_i")
                + ", where "
                + math_inline(r"|L_i^{(1)}|=\operatorname{int}\left[\frac{1}{2}|L_i|\right]")
                + ", and the order is preserved.</li>"
                "<li>Define the variance of "
                + math_inline(r"L_i^{(j)}")
                + ", "
                + math_inline("j=1,2")
                + ", as the quadratic form "
                + math_inline(r"\tilde V_i^{(j)}\equiv \tilde w_i^{(j)\prime}V_i^{(j)}\tilde w_i^{(j)}")
                + ", where "
                + math_inline(r"V_i^{(j)}")
                + " is the covariance matrix between the constituents of the "
                + math_inline(r"L_i^{(j)}")
                + " bisection, and "
                + math_inline(r"\tilde w_i^{(j)}=\frac{\operatorname{diag}[V_i^{(j)}]^{-1}}{\operatorname{tr}[\operatorname{diag}[V_i^{(j)}]^{-1}]}")
                + ", where "
                + math_inline(r"\operatorname{diag}[\cdot]")
                + " and "
                + math_inline(r"\operatorname{tr}[\cdot]")
                + " are the diagonal and trace operators.</li>"
                "<li>Compute the split factor: "
                + math_inline(r"\alpha_i=1-\frac{\tilde V_i^{(1)}}{\tilde V_i^{(1)}+\tilde V_i^{(2)}}")
                + ", so that "
                + math_inline(r"0\le\alpha_i\le1")
                + ".</li>"
                "<li>Re-scale allocations "
                + math_inline(r"w_n")
                + " by a factor of "
                + math_inline(r"\alpha_i")
                + ", "
                + math_inline(r"\forall n\in L_i^{(1)}")
                + ".</li>"
                "<li>Re-scale allocations "
                + math_inline(r"w_n")
                + " by a factor of "
                + math_inline(r"1-\alpha_i")
                + ", "
                + math_inline(r"\forall n\in L_i^{(2)}")
                + ".</li>"
                "</ol></li>"
                "<li>Loop to step 2.</li>"
                "</ol>"
            )
        if block.kind == "olist" and block.lines and (
            block.lines[0].startswith("For each Li") or block.lines[0].startswith("Loop to step 2")
        ):
            return ""
    if chapter.slug == "chapter-15":
        if block.kind == "ulist" and block.lines and block.lines[0].startswith("a = (n + 𝜃"):
            return math_display(
                r"\begin{aligned}"
                r"a&=(n+\theta^2)(\pi_+-\pi_-)^2\\"
                r"b&=\left[2n\pi_- - \theta^2(\pi_+-\pi_-)\right](\pi_+-\pi_-)\\"
                r"c&=n\pi_-^2"
                r"\end{aligned}"
            )
        if block.kind == "olist" and block.lines and block.lines[0].startswith("For iterations i ="):
            return (
                "<ol>"
                "<li>For iterations "
                r'<span class="math inline">\(i=1,\ldots,I\)</span>'
                ":"
                "<ol type=\"a\">"
                "<li>Draw "
                r'<span class="math inline">\(\lfloor nk\rfloor\)</span>'
                " samples from "
                r'<span class="math inline">\(\{\pi_t\}_{t=1,\ldots,T}\)</span>'
                " with replacement, where "
                r'<span class="math inline">\(k\)</span>'
                " is the number of years used by investors to assess a strategy (e.g., 2 years). We denote the set of these drawn samples as "
                r'<span class="math inline">\(\{\pi_j^{(i)}\}_{j=1,\ldots,\lfloor nk\rfloor}\)</span>'
                ".</li>"
                "<li>Derive the observed precision from iteration "
                r'<span class="math inline">\(i\)</span>'
                " as "
                r'<span class="math inline">\(p_i=\frac{1}{\lfloor nk\rfloor}\left\|\{\pi_j^{(i)}\mid\pi_j^{(i)}>0\}_{j=1,\ldots,\lfloor nk\rfloor}\right\|\)</span>'
                ".</li>"
                "</ol>"
                "</li>"
                "<li>Fit the PDF of "
                r'<span class="math inline">\(p\)</span>'
                ", denoted "
                r'<span class="math inline">\(f[p]\)</span>'
                ", by applying a Kernel Density Estimator (KDE) on "
                r'<span class="math inline">\(\{p_i\}_{i=1,\ldots,I}\)</span>'
                ".</li>"
                "</ol>"
            )
    if chapter.slug == "chapter-02" and block.kind == "olist" and block.lines:
        if block.lines[0].startswith("Rebalance costs:"):
            return (
                "<ol>"
                "<li><strong>Rebalance costs:</strong> The variable cost "
                r'<span class="math inline">\(\{c_t\}\)</span>'
                " associated with the allocation rebalance is "
                r'<span class="math inline">\(c_t=\sum_{i=1}^{I}(|h_{i,t-1}|p_{i,t}+|h_{i,t}|o_{i,t+1})\varphi_{i,t}\tau_i,\ \forall t\in B\)</span>'
                ". We do not embed "
                r'<span class="math inline">\(c_t\)</span>'
                " in "
                r'<span class="math inline">\(K_t\)</span>'
                ", or shorting the spread will generate fictitious profits when the allocation is rebalanced. In your code, you can treat "
                r'<span class="math inline">\(\{c_t\}\)</span>'
                " as a (negative) dividend.</li>"
                "<li><strong>Bid-ask spread:</strong> The cost "
                r'<span class="math inline">\(\{\tilde{c}_t\}\)</span>'
                " of buying or selling one unit of this virtual ETF is "
                r'<span class="math inline">\(\tilde{c}_t=\sum_{i=1}^{I}|h_{i,t-1}|p_{i,t}\varphi_{i,t}\tau_i\)</span>'
                ". When a unit is bought or sold, the strategy must charge this cost "
                r'<span class="math inline">\(\tilde{c}_t\)</span>'
                ", which is equivalent to crossing the bid-ask spread of this virtual ETF.</li>"
                "<li><strong>Volume:</strong> The volume traded "
                r'<span class="math inline">\(\{v_t\}\)</span>'
                " is determined by the least active member in the basket. Let "
                r'<span class="math inline">\(v_{i,t}\)</span>'
                " be the volume traded by instrument "
                r'<span class="math inline">\(i\)</span>'
                " over bar "
                r'<span class="math inline">\(t\)</span>'
                ". The number of tradeable basket units is "
                r'<span class="math inline">\(v_t=\min_i\{v_{i,t}/|h_{i,t-1}|\}\)</span>'
                ".</li>"
                "</ol>"
            )
    return None


def chapter_table_html(chapter: Chapter, block: Block) -> str | None:
    if chapter.slug == "chapter-01" and block.caption.startswith("Table 1.1:"):
        return (
            f'<figure class="table-figure"><figcaption>{html.escape(block.caption)}</figcaption>'
            f'<div class="table-wrap">{table_1_1_html()}</div></figure>'
        )
    if chapter.slug == "chapter-01" and block.caption.startswith("Table 1.2:"):
        return (
            f'<figure class="table-figure"><figcaption>{html.escape(block.caption)}</figcaption>'
            f'<div class="table-wrap">{table_1_2_html()}</div></figure>'
        )
    if chapter.slug == "chapter-02" and block.caption.startswith("Table 2.1:"):
        return ""
    if chapter.slug == "chapter-05" and block.caption.startswith("Table 5.1:"):
        table = block.text.replace("<thead><tr>", '<thead><tr><th scope="col">Contract</th>', 1)
        if "<tbody>" in table:
            head, body = table.split("<tbody>", 1)
            body = re.sub(r"<tr><td>([^<]+)</td>", r'<tr><th scope="row">\1</th>', body)
            table = head + "<tbody>" + body
        return (
            f'<figure class="table-figure"><figcaption>{html.escape(block.caption)}</figcaption>'
            f'<div class="table-wrap">{table}</div></figure>'
        )
    if chapter.slug == "chapter-13":
        override = chapter_13_table_html(block)
        if override is not None:
            return override
    if chapter.slug == "chapter-17" and block.caption.startswith("Table 17.1:"):
        return (
            f'<figure class="table-figure"><figcaption>{html.escape(block.caption)}</figcaption>'
            f'<div class="table-wrap">{table_17_1_html()}</div></figure>'
        )
    return None


def token_class(tok_type: int, tok_string: str, previous_name: str | None) -> str:
    if tok_type == tokenize.COMMENT:
        return "co"
    if tok_type == tokenize.STRING:
        return "st"
    if tok_type == token.NUMBER:
        return "dv"
    if tok_type == token.OP:
        return "op"
    if tok_type == token.NAME:
        if keyword.iskeyword(tok_string):
            return "kw"
        if previous_name in {"def", "class"}:
            return "fu"
        if tok_string in {"True", "False", "None"}:
            return "cn"
        return "va"
    return ""


def highlighted_python_html(source: str) -> str:
    lines = source.splitlines(keepends=True) or [""]
    out: list[str] = []
    last_row, last_col = 1, 0
    previous_name: str | None = None

    try:
        tokens = tokenize.generate_tokens(io.StringIO(source).readline)
        for tok in tokens:
            if tok.type in {tokenize.ENCODING, token.ENDMARKER}:
                continue
            start_row, start_col = tok.start
            end_row, end_col = tok.end
            if start_row > len(lines):
                continue
            if start_row > last_row:
                out.append(html.escape(lines[last_row - 1][last_col:]))
                for row in range(last_row + 1, start_row):
                    out.append(html.escape(lines[row - 1]))
                out.append(html.escape(lines[start_row - 1][:start_col]))
            else:
                out.append(html.escape(lines[start_row - 1][last_col:start_col]))

            cls = token_class(tok.type, tok.string, previous_name)
            token_text = html.escape(tok.string)
            out.append(f'<span class="{cls}">{token_text}</span>' if cls else token_text)
            if tok.type == token.NAME:
                previous_name = tok.string
            elif tok.type not in {tokenize.NL, tokenize.NEWLINE, token.INDENT, token.DEDENT}:
                previous_name = None
            last_row, last_col = end_row, end_col

        if last_row <= len(lines):
            out.append(html.escape(lines[last_row - 1][last_col:]))
            for row in range(last_row + 1, len(lines) + 1):
                out.append(html.escape(lines[row - 1]))
        return "".join(out)
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return html.escape(source)


def leading_spaces(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def split_outside_syntax(line: str, separator: str) -> list[str]:
    parts: list[str] = []
    start = 0
    quote = ""
    escaped = False
    bracket_depth = 0
    for index, ch in enumerate(line):
        if quote:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == quote:
                quote = ""
            continue
        if ch in {"'", '"'}:
            quote = ch
            continue
        if ch == "#":
            break
        if ch in "([{":
            bracket_depth += 1
            continue
        if ch in ")]}":
            bracket_depth = max(0, bracket_depth - 1)
            continue
        if ch == separator and bracket_depth == 0:
            parts.append(line[start:index])
            start = index + 1
    parts.append(line[start:])
    return parts


def expand_inline_suite(line: str) -> list[str]:
    stripped = line.lstrip(" ")
    if not re.match(r"(if|elif|else|for|while|try|except|finally|with)\b", stripped):
        return [line]
    indent = line[: len(line) - len(stripped)]
    parts = split_outside_syntax(stripped, ":")
    if len(parts) != 2 or not parts[1].strip():
        return [line]
    return [indent + parts[0].rstrip() + ":", indent + "    " + parts[1].strip()]


def split_semicolon_statements(line: str) -> list[str]:
    parts = split_outside_syntax(line, ";")
    if len(parts) == 1:
        return [line]
    indent = line[: leading_spaces(line)]
    return [indent + part.strip() for part in parts if part.strip()]


def normalize_code_source(lines: list[str]) -> str:
    expanded = [line.expandtabs(4).rstrip() for line in lines]
    nonblank = [line for line in expanded if line.strip()]
    if nonblank:
        min_indent = min(leading_spaces(line) for line in nonblank)
        if min_indent:
            expanded = [line[min_indent:] if len(line) >= min_indent else "" for line in expanded]
    normalized: list[str] = []
    for line in expanded:
        indent = leading_spaces(line)
        if indent and indent % 4:
            remainder = indent % 4
            adjusted = indent - remainder if remainder <= 2 else indent + (4 - remainder)
            adjusted = max(4, adjusted)
            line = " " * adjusted + line[indent:]
        if not line.strip():
            normalized.append("")
            continue
        for suite_line in expand_inline_suite(line):
            normalized.extend(split_semicolon_statements(suite_line))
    return "\n".join(normalized).rstrip()


def normalize_python_glyphs(source: str) -> str:
    source = source.replace("’’’", "'''").replace("‘‘‘", "'''")
    source = source.replace("“““", '"""').replace("”””", '"""')
    source = source.replace("’", "'").replace("‘", "'")
    source = source.replace("–", "-").replace("—", "-").replace("−", "-")
    source = re.sub(r"\bfrom\s+([A-Za-z_][A-Za-z0-9_.]*)import\b", r"from \1 import", source)
    return source


def looks_like_python_source(source: str) -> bool:
    for line in source.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith((">>>", "...", "#", "@", "def ", "class ", "return ", "import ", "from ", "print ")):
            return True
        if re.match(r"^(if|elif|else|for|while|try|except|finally|with|assert|raise|yield|continue|break)\b", stripped):
            return True
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*\s*=", stripped):
            return True
    return False


def filter_exercise_blocks(blocks: list[Block], sections: list[Block]) -> tuple[list[Block], list[Block]]:
    end_markers = {"REFERENCES", "REFERENCE", "BIBLIOGRAPHY", "APPENDICES", "INDEX"}
    filtered: list[Block] = []
    skipping = False
    for block in blocks:
        label = block.text.strip().upper() if block.kind in {"p", "heading"} else ""
        if not skipping and label == "EXERCISES":
            skipping = True
            continue
        if skipping and label in end_markers:
            skipping = False
        if not skipping:
            filtered.append(block)
    kept = {id(block) for block in filtered}
    return filtered, [section for section in sections if id(section) in kept]


def parse_chapter(chapter: Chapter, pages: list[list[str]], image_map: dict[int, list[str]]) -> tuple[list[Block], list[Block]]:
    blocks: list[Block] = []
    sections: list[Block] = []
    para: list[str] = []
    chapter_images = {page: list(image_map.get(page, [])) for page in range(chapter.start, chapter.end + 1)}
    events: list[tuple[str, int, str]] = []
    for page_no in range(chapter.start, chapter.end + 1):
        events.append(("anchor", page_no, ""))
        for line in page_body_lines(pages[page_no - 1], chapter, page_no):
            events.append(("line", page_no, line))

    current_page = chapter.start
    previous_page: int | None = None
    in_reference_source = False
    i = 0
    while i < len(events):
        kind, page_no, line = events[i]
        if kind == "anchor":
            emit_paragraph(blocks, para)
            if previous_page is not None:
                for src in chapter_images.get(previous_page, []):
                    blocks.append(Block("figure", caption="", src=src))
                chapter_images[previous_page] = []
            current_page = page_no
            previous_page = page_no
            blocks.append(Block("page-anchor", section_id=f"pdf-page-{page_no}"))
            i += 1
            continue

        stripped = line.strip()
        if not stripped:
            emit_paragraph(blocks, para)
            i += 1
            continue

        if in_reference_source and is_part_opener_line(stripped):
            emit_paragraph(blocks, para)
            break

        if is_special_heading(stripped):
            emit_paragraph(blocks, para)
            section_id = slugify(stripped)
            block = Block("heading", text=stripped, level=2, section_id=section_id)
            blocks.append(block)
            sections.append(block)
            in_reference_source = reference_heading_label(stripped) is not None
            i += 1
            continue

        if in_reference_source:
            para.append(line)
            i += 1
            continue

        if is_visual_artifact_line(line):
            emit_paragraph(blocks, para)
            i += 1
            continue

        snippet = SNIPPET_RE.match(stripped)
        if snippet:
            emit_paragraph(blocks, para)
            caption_text = snippet.group(2).strip()
            i += 1
            while i < len(events):
                next_kind, _, candidate = events[i]
                if next_kind == "anchor" or not candidate.strip():
                    i += 1
                    continue
                if not is_caption_continuation(candidate):
                    break
                caption_text += " " + candidate.strip()
                i += 1
            caption = f"Snippet {snippet.group(1)}: {format_caption(caption_text)}"
            code: list[str] = []
            in_triple_quote = False
            bracket_depth = 0
            pending_backslash = False
            while i < len(events):
                next_kind, _, candidate = events[i]
                if next_kind == "anchor":
                    i += 1
                    continue
                candidate_stripped = candidate.strip()
                in_code_context = in_triple_quote or bracket_depth > 0 or pending_backslash
                if not candidate_stripped:
                    next_i = next_significant_event(events, i + 1)
                    if code and (
                        not in_code_context
                        and (
                            next_i is None
                            or section_heading_match(events[next_i][2].strip(), chapter)
                            or SNIPPET_RE.match(events[next_i][2].strip())
                            or TABLE_RE.match(events[next_i][2].strip())
                            or FIGURE_RE.match(events[next_i][2].strip())
                            or (
                                not is_code_like(events[next_i][2])
                                and not is_code_continuation_line(events[next_i][2])
                            )
                        )
                    ):
                        break
                    if code and in_code_context:
                        code.append("")
                    i += 1
                    continue
                if (
                    not in_code_context
                    and (
                        section_heading_match(candidate_stripped, chapter)
                        or SNIPPET_RE.match(candidate_stripped)
                        or TABLE_RE.match(candidate_stripped)
                        or FIGURE_RE.match(candidate_stripped)
                    )
                ):
                    break
                if in_code_context and FIGURE_RE.match(candidate_stripped):
                    i += 1
                    continue
                line_is_code = in_code_context or (
                    not is_prose_line(candidate)
                    and (is_code_like(candidate) or (bool(code) and is_code_continuation_line(candidate)))
                )
                if code and not line_is_code:
                    if is_prose_line(candidate) or not candidate.startswith(("    ", "\t")):
                        break
                code.append(candidate.rstrip())
                if triple_quote_count(candidate) % 2:
                    in_triple_quote = not in_triple_quote
                bracket_depth = max(0, bracket_depth + bracket_delta(candidate))
                pending_backslash = candidate.rstrip().endswith("\\")
                i += 1
            blocks.append(Block("code", caption=caption, lines=code))
            continue

        table = TABLE_RE.match(stripped)
        if table:
            emit_paragraph(blocks, para)
            caption = f"Table {table.group(1)}: {table.group(2)}"
            i += 1
            rows: list[str] = []
            while i < len(events):
                next_kind, _, candidate = events[i]
                if next_kind == "anchor":
                    i += 1
                    continue
                candidate_stripped = candidate.strip()
                if not candidate_stripped:
                    i += 1
                    if rows:
                        j = i
                        while j < len(events) and (events[j][0] == "anchor" or not events[j][2].strip()):
                            j += 1
                        if j < len(events) and not is_table_row_like(events[j][2]):
                            break
                    continue
                if (
                    rows
                    and not is_table_row_like(candidate)
                    and not candidate.startswith(" ")
                ):
                    break
                if section_heading_match(candidate_stripped, chapter) or FIGURE_RE.match(candidate_stripped):
                    break
                rows.append(candidate)
                i += 1
            blocks.append(Block("table", caption=caption, text=parse_table(rows)))
            continue

        figure = FIGURE_RE.match(stripped)
        if figure:
            emit_paragraph(blocks, para)
            caption = f"Figure {figure.group(1)}: {figure.group(2)}"
            src = chapter_images.get(current_page, []).pop(0) if chapter_images.get(current_page) else ""
            blocks.append(Block("figure", caption=caption, src=src))
            i += 1
            continue

        section = section_heading_match(stripped, chapter)
        if section:
            emit_paragraph(blocks, para)
            number, title = section.groups()
            level = 2 + min(number.count(".") - 1, 2)
            section_id = "sec-" + number.replace(".", "-")
            block = Block("heading", text=f"{number} {title.title() if title.isupper() else title}", level=level, section_id=section_id)
            blocks.append(block)
            if level <= 3:
                sections.append(block)
            i += 1
            continue

        if is_mathish(line):
            emit_paragraph(blocks, para)
            formula = [line.rstrip()]
            i += 1
            while i < len(events):
                next_kind, _, candidate = events[i]
                if next_kind == "anchor":
                    i += 1
                    continue
                if not is_mathish(candidate):
                    break
                formula.append(candidate.rstrip())
                i += 1
            blocks.append(Block("math", lines=formula))
            continue

        bullet = re.match(r"^\s*(?:r|•|◦)\s+(.+)$", line)
        numbered = re.match(r"^\s*(\d+)\.\s+(.+)$", line)
        if bullet or numbered:
            emit_paragraph(blocks, para)
            ordered = bool(numbered)
            items: list[str] = []
            while i < len(events):
                next_kind, _, current = events[i]
                if next_kind == "anchor":
                    i += 1
                    continue
                b = re.match(r"^\s*(?:r|•|◦)\s+(.+)$", current)
                n = re.match(r"^\s*(\d+)\.\s+(.+)$", current)
                if ordered and n:
                    items.append(n.group(2).strip())
                elif not ordered and b:
                    items.append(b.group(1).strip())
                elif items and current.startswith("      ") and current.strip():
                    items[-1] += " " + current.strip()
                else:
                    break
                i += 1
            blocks.append(Block("olist" if ordered else "ulist", lines=items))
            continue

        para.append(line)
        i += 1

    emit_paragraph(blocks, para)
    if previous_page is not None:
        for src in chapter_images.get(previous_page, []):
            blocks.append(Block("figure", caption="", src=src))
        chapter_images[previous_page] = []
    return blocks, sections


def nav_html(active: Chapter) -> str:
    parts: list[str] = ['<nav class="book-nav" aria-label="Table of contents">']
    last_part = None
    for chapter in CHAPTERS:
        if chapter.part and chapter.part != last_part:
            parts.append(f'<div class="book-part">{html.escape(chapter.part)}</div>')
            last_part = chapter.part
        cls = "active" if chapter.file == active.file else ""
        parts.append(f'<a class="{cls}" href="{chapter.file}">{html.escape(chapter.title)}</a>')
    parts.append("</nav>")
    return "\n".join(parts)


def block_html(block: Block, chapter: Chapter, math_index: int = -1) -> str:
    if block.kind == "page-anchor":
        return f'<span class="pdf-page-anchor" id="{block.section_id}"></span>'
    if block.kind == "p":
        return style_citations_html(chapter_paragraph_html(chapter, block.text) or "")
    if block.kind == "heading":
        level = min(max(block.level, 2), 4)
        heading_text = block.text.replace("Shannon’S", "Shannon’s")
        if chapter.slug == "chapter-01":
            heading_text = {
                "sec-1-2": "1.2 The Main Reason Financial Machine Learning Projects Usually Fail",
            }.get(block.section_id, heading_text)
        if chapter.slug == "chapter-07":
            heading_text = {
                "sec-7-2": "7.2 The Goal of Cross-Validation",
                "sec-7-3": "7.3 Why K-Fold CV Fails in Finance",
                "sec-7-4": "7.4 A Solution: Purged K-Fold CV",
                "sec-7-5": "7.5 Bugs in Sklearn's Cross-Validation",
            }.get(block.section_id, heading_text)
        if chapter.slug == "chapter-08":
            heading_text = {
                "sec-8-2": "8.2 The Importance of Feature Importance",
                "sec-8-3": "8.3 Feature Importance with Substitution Effects",
                "sec-8-4": "8.4 Feature Importance without Substitution Effects",
                "sec-8-5": "8.5 Parallelized vs. Stacked Feature Importance",
                "sec-8-6": "8.6 Experiments with Synthetic Data",
            }.get(block.section_id, heading_text)
        if chapter.slug == "chapter-09":
            heading_text = {
                "sec-9-2": "9.2 Grid Search Cross-Validation",
                "sec-9-3": "9.3 Randomized Search Cross-Validation",
                "sec-9-3-1": "9.3.1 Log-Uniform Distribution",
                "sec-9-4": "9.4 Scoring and Hyper-Parameter Tuning",
            }.get(block.section_id, heading_text)
        if chapter.slug == "chapter-11":
            heading_text = {
                "sec-11-3": "11.3 Even If Your Backtest Is Flawless, It Is Probably Wrong",
            }.get(block.section_id, heading_text)
        if chapter.slug == "chapter-12":
            heading_text = {
                "sec-12-5": "12.5 How Combinatorial Purged Cross-Validation Addresses Backtest Overfitting",
            }.get(block.section_id, heading_text)
        if chapter.slug == "chapter-19":
            heading_text = {
                "sec-19-6": "19.6 Additional Features from Microstructural Datasets",
                "sec-19-6-1": "19.6.1 Distribution of Order Sizes",
            }.get(block.section_id, heading_text)
        if chapter.slug == "chapter-20":
            heading_text = {
                "sec-20-3": "20.3 Single-Thread Vs. Multithreading Vs. Multiprocessing",
            }.get(block.section_id, heading_text)
        if chapter.slug == "chapter-22":
            heading_text = {
                "sec-22-2": "22.2 Regulatory Response to the Flash Crash of 2010",
                "sec-22-4": "22.4 HPC Hardware",
                "sec-22-5": "22.5 HPC Software",
                "sec-22-6-6": "22.6.6 Revealing High Frequency Events with Non-uniform Fast Fourier Transform",
                "sec-22-7": "22.7 Summary and Call for Participation",
            }.get(block.section_id, heading_text)
        return f'<h{level} id="{block.section_id}">{html.escape(heading_text)}</h{level}>'
    if block.kind == "math":
        override = chapter_math_override(chapter, math_index)
        if override is not None:
            return math_display(override) if override else ""
        return formula_block_html(chapter, block.lines)
    if block.kind == "code":
        caption = block.caption
        if chapter.slug == "chapter-11" and caption.startswith("Snippet 11.1:"):
            return chapter_11_snippet_html()
        if chapter.slug == "chapter-14" and caption.startswith("Snippet 14.5:"):
            return chapter_14_snippet_14_5_html()
        if chapter.slug == "chapter-04":
            caption = caption.replace("Random T1 Series", "Random t1 Series")
        if chapter.slug == "chapter-17" and caption.startswith("Snippet 17.1:"):
            caption = caption.replace("Sadf", "SADF")
        if chapter.slug == "chapter-19" and caption.startswith("Snippet 19.1:"):
            caption = caption.replace("Corwin-schultz", "Corwin-Schultz")
        caption_html = html.escape(caption)
        if chapter.slug == "chapter-21" and caption.startswith("Snippet 21.2:"):
            caption_html = "Snippet 21.2: Set " + math_inline(r"\Omega") + " of All Vectors Associated with All Partitions"
        code_text = chapter_code_override(chapter, block.caption) or normalize_code_source(block.lines)
        language = "python" if looks_like_python_source(code_text) else "text"
        if language == "python":
            code_text = normalize_python_glyphs(code_text)
        code_body = highlighted_python_html(code_text) if language == "python" else html.escape(code_text)
        return (
            '<figure class="code-listing">'
            f"<figcaption>{caption_html}</figcaption>"
            '<button class="copy-code" type="button">Copy</button>'
            f'<div class="sourceCode"><pre class="sourceCode {language}"><code class="sourceCode {language}">'
            + code_body
            + "</code></pre></div></figure>"
        )
    if block.kind == "table":
        override = chapter_table_html(chapter, block)
        if override is not None:
            return override
        return (
            f'<figure class="table-figure"><figcaption>{html.escape(block.caption)}</figcaption>'
            f'<div class="table-wrap">{block.text}</div></figure>'
        )
    if block.kind == "figure":
        if chapter.slug == "chapter-02":
            override = chapter_02_block_figure_html(block)
            if override is not None:
                return override
        if chapter.slug == "chapter-03":
            override = chapter_03_block_figure_html(block)
            if override is not None:
                return override
        if chapter.slug == "chapter-04":
            override = chapter_04_block_figure_html(block)
            if override is not None:
                return override
        if chapter.slug == "chapter-05":
            override = chapter_05_block_figure_html(block)
            if override is not None:
                return override
        if chapter.slug == "chapter-06":
            override = chapter_06_block_figure_html(block)
            if override is not None:
                return override
        if chapter.slug == "chapter-07":
            override = chapter_07_block_figure_html(block)
            if override is not None:
                return override
        if chapter.slug == "chapter-08":
            override = chapter_08_block_figure_html(block)
            if override is not None:
                return override
        if chapter.slug == "chapter-10":
            override = chapter_10_block_figure_html(block)
            if override is not None:
                return override
        if chapter.slug == "chapter-11":
            override = chapter_11_block_figure_html(block)
            if override is not None:
                return override
        if chapter.slug == "chapter-12":
            override = chapter_12_block_figure_html(block)
            if override is not None:
                return override
        if chapter.slug == "chapter-13":
            override = chapter_13_block_figure_html(block)
            if override is not None:
                return override
        if chapter.slug == "chapter-14":
            override = chapter_14_block_figure_html(block)
            if override is not None:
                return override
        if chapter.slug == "chapter-15":
            override = chapter_15_block_figure_html(block)
            if override is not None:
                return override
        if chapter.slug == "chapter-16":
            override = chapter_16_block_figure_html(block)
            if override is not None:
                return override
        if chapter.slug == "chapter-17":
            override = chapter_17_block_figure_html(block)
            if override is not None:
                return override
        if chapter.slug == "chapter-18":
            override = chapter_18_block_figure_html(block)
            if override is not None:
                return override
        if chapter.slug == "chapter-19":
            override = chapter_19_block_figure_html(block)
            if override is not None:
                return override
        if chapter.slug == "chapter-20":
            override = chapter_20_block_figure_html(block)
            if override is not None:
                return override
        if chapter.slug == "chapter-21":
            override = chapter_21_block_figure_html(block)
            if override is not None:
                return override
        if chapter.slug == "chapter-22":
            override = chapter_22_block_figure_html(block)
            if override is not None:
                return override
        if chapter.slug == "front-matter" and block.src == "media/afml-1_1.jpg":
            return (
                '<figure class="book-cover">'
                '<img src="media/afml-1_1.jpg" alt="Cover of Advances in Financial Machine Learning">'
                "</figure>"
            )
        if not block.src:
            return f'<figure><figcaption>{html.escape(block.caption)}</figcaption></figure>'
        caption = f"<figcaption>{html.escape(block.caption)}</figcaption>" if block.caption else ""
        return f'<figure class="book-figure"><img src="{html.escape(block.src)}" alt="{html.escape(block.caption)}">{caption}</figure>'
    if block.kind in {"ulist", "olist"}:
        override = chapter_list_html(chapter, block)
        if override is not None:
            return override
        tag = "ol" if block.kind == "olist" else "ul"
        if chapter.slug == "chapter-02":
            items = "".join(f"<li>{mathify_chapter_02_text(join_paragraph_lines([item]))}</li>" for item in block.lines)
        else:
            items = "".join(f"<li>{mathify_general_text(join_paragraph_lines([item]))}</li>" for item in block.lines)
        return f"<{tag}>{items}</{tag}>"
    return ""


def style_citations_html(rendered: str) -> str:
    return re.sub(r"\[(\d{4}[a-z]?)\]", r'<span class="citation">[\1]</span>', rendered)


def reference_heading_label(text: str) -> str | None:
    markers = {
        "REFERENCES": "References",
        "REFERENCE": "Reference",
        "BIBLIOGRAPHY": "Bibliography",
    }
    return markers.get(text.strip().upper())


REFERENCE_SPLIT_RE = re.compile(
    r"(?<=\.)(?<![A-Z]\.)\s+(?=[A-ZÀ-ÖØ-Þ][^()]{0,180}\(\d{4}[a-z]?\))"
)
REFERENCE_START_RE = re.compile(
    r"^[A-ZÀ-ÖØ-Þ][^()]{0,180}(?:\(\d{4}[a-z]?\)|\b[12]\d{3}\.)"
)


def split_reference_entries(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", text).strip()
    normalized = re.sub(r"\s+[\u0300-\u036f]*Zbikowski, K\.", " Zbikowski, K.", normalized)
    if not normalized:
        return []
    entries: list[str] = []
    for part in REFERENCE_SPLIT_RE.split(normalized):
        part = part.strip()
        if not part:
            continue
        marker = " Bethel, E. W., Leinweber."
        if marker in part:
            before, after = part.split(marker, 1)
            entries.extend([before.strip(), ("Bethel, E. W., Leinweber." + after).strip()])
        else:
            entries.append(part)
    return [entry for entry in entries if entry]


def clean_reference_entry(entry: str) -> str:
    entry = unicodedata.normalize("NFC", entry).strip()
    entry = re.sub(r"(?:^|\s+)PART\s+\d+\b.*$", "", entry).strip()
    entry = entry.replace("loglinear", "log-linear")
    entry = entry.replace("http://www .alacra.com", "http://www.alacra.com")
    entry = entry.replace("http:// citeseerx.ist.psu.edu", "http://citeseerx.ist.psu.edu")
    entry = entry.replace("abstract= 2308659", "abstract=2308659")
    entry = entry.replace("MSCI_Barra_Factor%20Indices_ Methodology", "MSCI_Barra_Factor%20Indices_Methodology")
    entry = entry.replace("2016. 1154108", "2016.1154108")
    entry = re.sub(r"([A-Za-z0-9_-])\s+\.(com|org|net|edu|gov)\b", r"\1.\2", entry)
    entry = re.sub(r"([A-Za-z0-9_-])\.\s+(com|org|net|edu|gov)\b", r"\1.\2", entry)
    entry = re.sub(r"([A-Za-z0-9_-])\s+\.(\d{4})", r"\1.\2", entry)
    entry = re.sub(r"https?://\s+", lambda m: m.group(0).replace(" ", ""), entry)
    entry = re.sub(r"/\s+(abstract|doi|pdfplus)\b", r"/\1", entry)
    entry = entry.replace("Available at ttps://", "Available at https://")
    entry = entry.replace(" ttps://", " https://")
    while entry and unicodedata.category(entry[0]).startswith("M"):
        entry = entry[1:].lstrip()
    return entry


def linkify_reference_entry(entry: str) -> str:
    escaped = html.escape(entry)

    def replace_url(match: re.Match[str]) -> str:
        url = match.group(0).rstrip(".,);")
        trailing = match.group(0)[len(url) :]
        return f'<a href="{url}">{url}</a>{trailing}'

    return re.sub(r"https?://[^\s<]+", replace_url, escaped)


def append_reference_text(entries: list[str], text: str) -> None:
    for entry in split_reference_entries(text):
        entry = clean_reference_entry(entry)
        if not entry:
            continue
        if entries and entry.startswith("D., Rubel") and entries[-1].startswith("Bethel, E. W."):
            entries[-1] = clean_reference_entry(f"{entries[-1]} {entry}")
        elif entry.startswith("Bethel, E. W., Leinweber."):
            entries.append(entry)
        elif entries and entry.startswith("DOI:"):
            entries[-1] = clean_reference_entry(f"{entries[-1]} {entry}")
        elif entries and (entry.startswith("Available at ") or not REFERENCE_START_RE.match(entry)):
            entries[-1] = clean_reference_entry(f"{entries[-1]} {entry}")
        else:
            entries.append(entry)


def chapter_22_references_html() -> str:
    def e(text: str) -> str:
        return html.escape(text)

    entries = [
        e("Aad, G., et al. (2016): “Measurements of the Higgs boson production and decay rates and coupling strengths using pp collision data at ")
        + math_inline(r"\sqrt{s}=7")
        + e(" and ")
        + math_inline(r"8\,\mathrm{TeV}")
        + e(" in the ATLAS experiment.” The European Physical Journal C, Vol. 76, No. 1, p. 6."),
        e("Abbott, B.P. et al. (2016): “Observation of gravitational waves from a binary black hole merger.” Physical Review Letters, Vol. 116, No. 6, p. 061102."),
        e("Armbrust, M., et al. (2010): “A view of cloud computing.” Communications of the ACM, Vol. 53, No. 4, pp. 50-58."),
        e("Asanovic, K. et al. (2006): “The landscape of parallel computing research: A view from Berkeley.” Technical Report UCB/EECS-2006-183, EECS Department, University of California, Berkeley."),
        e("Ayachit, U. et al. “Performance analysis, design considerations, and applications of extreme-scale in situ infrastructures.” Proceedings of the International Conference for High Performance Computing, Networking, Storage and Analysis. IEEE Press."),
        e("Bethel, E. W. et al. (2011): “Federal market information technology in the post Flash Crash era: Roles for supercomputing.” Proceedings of WHPCF’2011. ACM. pp. 23-30."),
        e("Bloom, J. S. et al. (2012): “Automating discovery and classification of transients and variable stars in the synoptic survey era.” Publications of the Astronomical Society of the Pacific, Vol. 124, No. 921, p. 1175."),
        e("Camerer, C.F. and G. Loewenstein (2011): “Behavioral economics: Past, present, future.” In Advances in Behavioral Economics, pp. 1-52."),
        e("Chen, L. et al. (2015): “Profiling and understanding virtualization overhead in cloud.” Parallel Processing (ICPP), 2015 44th International Conference. IEEE."),
        e("Choi, J.Y. et al. (2013): ICEE: “Wide-area in transit data processing framework for near real-time scientific applications.” 4th SC Workshop on Petascale (Big) Data Analytics: Challenges and Opportunities in Conjunction with SC13."),
        e("Dong, Y. et al. (2012): “High performance network virtualization with SR-IOV.” Journal of Parallel and Distributed Computing, Vol. 72, No. 11, pp. 1471-1480."),
        e("Easley, D., M. Lopez de Prado, and M. O’Hara (2011): “The microstructure of the ‘Flash Crash’: Flow toxicity, liquidity crashes and the probability of informed trading.” Journal of Portfolio Management, Vol. 37, No. 2, pp. 118-128."),
        e("Folk, M. et al. (2011): “An overview of the HDF5 technology suite and its applications.” Proceedings of the EDBT/ICDT 2011 Workshop on Array Databases. ACM."),
        e("Fox, G. et al. (2015): “Big Data, simulations and HPC convergence, iBig Data benchmarking”: 6th International Workshop, WBDB 2015, Toronto, ON, Canada, June 16-17, 2015; and 7th International Workshop, WBDB 2015, New Delhi, India, December 14-15, 2015, Revised Selected Papers, T. Rabl, et al., eds. 2016, Springer International Publishing: Cham. pp. 3-17. DOI: 10.1007/978-3-319-49748-8_1."),
        e("Ghemawat, S., H. Gobioff, and S.-T. Leung (2003): “The Google file system,” SOSP ’03: Proceedings of the nineteenth ACM symposium on operating systems principles. ACM. pp. 29-43."),
        e("Gordon, A. et al. (2012): “ELI: Bare-metal performance for I/O virtualization.” SIGARCH Comput. Archit. News, Vol. 40, No. 1, pp. 411-422."),
        e("Gropp, W., E. Lusk, and A. Skjellum (1999): Using MPI: Portable Parallel Programming with the Message-Passing Interface. MIT Press."),
        e("Hey, T., S. Tansley, and K.M. Tolle (2009): The Fourth Paradigm: Data-Intensive Scientific Discovery. Vol. 1. Microsoft research Redmond, WA."),
        e("Hirschman, A. O. (1980): National Power and the Structure of Foreign Trade. Vol. 105. University of California Press."),
        e("Holzman, B. et al. (2017): “HEPCloud, a new paradigm for HEP facilities: CMS Amazon Web Services investigation.” Computing and Software for Big Science, Vol. 1, No. 1, p. 1."),
        e("Jackson, K. R., et al. (2010): “Performance analysis of high performance computing applications on the Amazon Web Services Cloud.” Cloud Computing Technology and Science (CloudCom). 2010 Second International Conference. IEEE."),
        e("Kim, T. et al. (2015): “Extracting baseline electricity usage using gradient tree boosting.” IEEE International Conference on Smart City/SocialCom/SustainCom (SmartCity). IEEE."),
        e("Kumar, V. et al. (1994): Introduction to Parallel Computing: Design and Analysis of Algorithms. Benjamin/Cummings Publishing Company."),
        e("Liu, Q. et al., (2014): “Hello ADIOS: The challenges and lessons of developing leadership class I/O frameworks.” Concurrency and Computation: Practice and Experience, Volume 26, No. 7, pp. 1453-1473."),
        e("National Academies of Sciences, Engineering and Medicine (2016): Future Directions for NSF Advanced Computing Infrastructure to Support U.S. Science and Engineering in 2017-2020. National Academies Press."),
        e("Nicholas, M. L. et al. (2009): “The Palomar transient factory: System overview, performance, and first results.” Publications of the Astronomical Society of the Pacific, Vol. 121, No. 886, p. 1395."),
        e("Qiu, J. et al. (2016): “A survey of machine learning for big data processing.” EURASIP Journal on Advances in Signal Processing, Vol. 2016, No. 1, p. 67. DOI: 10.1186/s13634-016-0355-x"),
        e("Rudin, C. and K. L. Wagstaff (2014) “Machine learning for science and society.” Machine Learning, Vol. 95, No. 1, pp. 1-9."),
        e("Shoshani, A. and D. Rotem (2010): “Scientific data management: Challenges, technology, and deployment.” Chapman & Hall/CRC Computational Science Series. CRC Press."),
        e("Snir, M. et al. (1998): MPI: The Complete Reference. Volume 1, The MPI-1 Core. MIT Press."),
        e("Song, J. H. et al. (2014): “Exploring irregular time series through non-uniform fast Fourier transform.” Proceedings of the 7th Workshop on High Performance Computational Finance, IEEE Press."),
        e("Todd, A. et al. (2014): “Insights from Smart Meters: The potential for peak hour savings from behavior-based programs.” Lawrence Berkeley National Laboratory. Available at https://www4.eere.energy.gov/seeaction/system/files/documents/smart_meters.pdf."),
        e("Wu, K. et al. (2013): “A big data approach to analyzing market volatility.” Algorithmic Finance. Vol. 2, No. 3, pp. 241-267."),
        e("Wu, L. et al. (2016): “Towards real-time detection and tracking of spatio-temporal features: Blob-filaments in fusion plasma.” IEEE Transactions on Big Data, Vol. 2, No. 3, pp. 262-275."),
        e("Yan, J. et al. (2009): “How much can behavioral targeting help online advertising?” Proceedings of the 18th international conference on world wide web. ACM. pp. 261-270."),
        e("Yelick, K., et al. (2011): “The Magellan report on cloud computing for science.” U.S. Department of Energy, Office of Science."),
        e("Zeff, R.L. and B. Aronson (1999): Advertising on the Internet. John Wiley & Sons."),
    ]
    items = "".join(f"<li>{entry}</li>" for entry in entries)
    return f'<ul class="references-list">{items}</ul>'


def references_list_html(entries: list[str], chapter: Chapter | None = None) -> str:
    if chapter is not None and chapter.slug == "chapter-22":
        return chapter_22_references_html()
    if chapter is not None and chapter.slug == "chapter-17":
        entries = [
            "Brown, R.L., J. Durbin, and J.M. Evans (1975): “Techniques for Testing the Constancy of Regression Relationships over Time.” Journal of the Royal Statistical Society: Series B, Vol. 37, No. 2, pp. 149-192."
            if entry.startswith("Brown, R.L., J. Durbin, and J.M. Evans")
            else entry
            for entry in entries
        ]
    if chapter is not None and chapter.slug == "chapter-18":
        fixed_entries = []
        for entry in entries:
            entry = entry.replace("Liquidity,information", "Liquidity, information")
            entry = entry.replace("Easley D.,", "Easley, D.,")
            entry = entry.replace("M. Kiefer and, M. O’Hara", "M. Kiefer, and M. O’Hara")
            entry = entry.replace("pp. 1547–1493", "pp. 1457–1493")
            entry = entry.replace("Bienestock", "Bienenstock")
            fixed_entries.append(entry)
        entries = fixed_entries
    items = "".join(f"<li>{linkify_reference_entry(entry)}</li>" for entry in entries)
    return f'<ul class="references-list">{items}</ul>'


def render_blocks(chapter: Chapter, blocks: list[Block]) -> str:
    parts: list[str] = []
    math_index = 0
    reference_entries: list[str] = []
    in_references = False

    def flush_references() -> None:
        nonlocal reference_entries
        if reference_entries:
            parts.append(references_list_html(reference_entries, chapter))
            reference_entries = []

    for block in blocks:
        if block.kind in {"p", "heading"}:
            reference_label = reference_heading_label(block.text)
            if reference_label is not None:
                flush_references()
                parts.append(f'<h2 class="references-heading" id="{slugify(reference_label)}">{reference_label}</h2>')
                in_references = True
                continue

        if in_references and block.kind == "page-anchor":
            continue
        if in_references and block.kind == "p":
            if chapter.slug == "chapter-04" and block.text.strip().startswith("Sample weighting is a common topic"):
                flush_references()
                parts.append(chapter_04_p(block.text))
                continue
            append_reference_text(reference_entries, block.text)
            continue
        if in_references and block.kind in {"ulist", "olist"}:
            for line in block.lines:
                append_reference_text(reference_entries, join_paragraph_lines([line]))
            continue
        if in_references:
            flush_references()
            in_references = False

        if block.kind == "math":
            rendered = block_html(block, chapter, math_index)
            math_index += 1
        else:
            rendered = block_html(block, chapter)
        if rendered:
            parts.append(rendered)
    flush_references()
    return "\n".join(parts)


def page_shell(chapter: Chapter, content: str, sections: list[Block]) -> str:
    idx = CHAPTERS.index(chapter)
    prev_chapter = CHAPTERS[idx - 1] if idx > 0 else None
    next_chapter = CHAPTERS[idx + 1] if idx < len(CHAPTERS) - 1 else None
    pager = '<div class="chapter-pager">'
    if prev_chapter:
        pager += f'<a href="{prev_chapter.file}">Previous: {html.escape(prev_chapter.title)}</a>'
    if next_chapter:
        pager += f'<a href="{next_chapter.file}">Next: {html.escape(next_chapter.title)}</a>'
    pager += "</div>"
    top_links: list[str] = ['<a href="index.html">Contents</a>']
    if prev_chapter:
        top_links.append(f'<a href="{prev_chapter.file}">Previous</a>')
    if next_chapter:
        top_links.append(f'<a href="{next_chapter.file}">Next</a>')
    top_nav = "\n".join(top_links)
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{html.escape(chapter.title)} | Advances in Financial Machine Learning</title>
    <link rel="stylesheet" href="../assets/afml-book.css?v={ASSET_VERSION}">
    <script>
      window.MathJax = {{
        tex: {{
          inlineMath: [['\\\\(', '\\\\)']],
          displayMath: [['\\\\[', '\\\\]']]
        }},
        svg: {{ fontCache: 'global' }}
      }};
    </script>
    <script defer src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js"></script>
    <script defer src="../assets/afml-book.js?v={ASSET_VERSION}"></script>
  </head>
  <body>
    <header class="book-topbar">
      <div>
        <a class="book-title" href="index.html">Advances in Financial Machine Learning</a>
        <span>{html.escape(chapter.part or "Book")}</span>
      </div>
      <nav aria-label="Book navigation">
        {top_nav}
      </nav>
    </header>
    <div class="book-layout">
      <main class="content">
        <article>
          <header class="chapter-header">
            <p>{html.escape(chapter.part)}</p>
            <h1>{html.escape(chapter.title)}</h1>
          </header>
          {content}
          {pager}
        </article>
      </main>
    </div>
  </body>
</html>
"""


def write_root_index() -> None:
    (ROOT / "index.html").write_text(
        """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta http-equiv="refresh" content="0; url=book/index.html">
    <title>Advances in Financial Machine Learning</title>
  </head>
  <body>
    <p><a href="book/index.html">Open Advances in Financial Machine Learning</a></p>
  </body>
</html>
""",
        encoding="utf-8",
    )


def chapter_number(chapter: Chapter) -> str:
    match = re.search(r"chapter-(\d+)", chapter.slug)
    return str(int(match.group(1))) if match else ""


SECTION_HEADING_RE = re.compile(r'<h(?P<level>[23]) id="(?P<id>sec-[^"]+)">(?P<title>.*?)</h(?P=level)>', re.S)
HTML_TAG_RE = re.compile(r"<[^>]+>")


def plain_text_from_html(fragment: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(HTML_TAG_RE.sub(" ", fragment))).strip()


def chapter_index_sections(chapter: Chapter) -> list[tuple[int, str, str]]:
    if not chapter.slug.startswith("chapter-"):
        return []
    path = BOOK / chapter.file
    if not path.exists():
        return []
    sections: list[tuple[int, str, str]] = []
    for match in SECTION_HEADING_RE.finditer(path.read_text(encoding="utf-8")):
        title = plain_text_from_html(match.group("title"))
        if title:
            sections.append((int(match.group("level")), match.group("id"), title))
    return sections


def write_book_index() -> None:
    grouped: dict[str, list[Chapter]] = {}
    for chapter in CHAPTERS:
        grouped.setdefault(chapter.part or "Front Matter", []).append(chapter)

    part_summaries = {
        "Preamble": "Scope, motivation, project failures, and the production-chain view of financial machine learning.",
        "Part 1: Data Analysis": "Financial data structures, labels, sample weights, and fractional differentiation.",
        "Part 2: Modelling": "Ensembles, cross-validation, feature importance, and hyper-parameter tuning.",
        "Part 3: Backtesting": "Bet sizing, backtest risks, synthetic data, statistics, strategy risk, and allocation.",
        "Part 4: Useful Financial Features": "Structural breaks, entropy, and microstructural features.",
        "Part 5: High-Performance Computing Recipes": "Parallelization, brute-force search, quantum computing, and HPC applications.",
        "Back Matter": "Generated book index.",
    }

    part_items: list[str] = []
    for part, chapters in grouped.items():
        heading = html.escape(part)
        summary = html.escape(part_summaries.get(part, ""))
        chapter_items: list[str] = []
        for chapter in chapters:
            number = chapter_number(chapter)
            number_html = f'<span class="toc-number">{html.escape(number)}</span>' if number else '<span class="toc-number toc-number-muted">i</span>'
            if chapter.slug == "index-back":
                number_html = '<span class="toc-number toc-number-muted">idx</span>'
            sections = chapter_index_sections(chapter)
            section_html = ""
            if sections:
                section_items = [
                    f'<li class="toc-section toc-section-level-{level}">'
                    f'<a href="{html.escape(chapter.file)}#{html.escape(section_id)}">{html.escape(title)}</a></li>'
                    for level, section_id, title in sections
                ]
                section_count = len(sections)
                label = "section" if section_count == 1 else "sections"
                section_html = (
                    f'<details class="toc-details"><summary>{section_count} {label}</summary>'
                    f'<ol class="toc-sections">{"".join(section_items)}</ol></details>'
                )
            section_search = " ".join(title for _, _, title in sections)
            searchable = f"{part} {chapter.title} {number} {section_search}".strip().lower()
            chapter_items.append(
                f'<li class="toc-chapter" data-toc-entry data-search="{html.escape(searchable)}">'
                f'<a class="toc-entry" href="{html.escape(chapter.file)}">'
                f'{number_html} <span>{html.escape(chapter.title)}</span></a>'
                f'{section_html}</li>'
            )
        part_items.append(
            '<li class="toc-part">'
            f'<div class="toc-part-heading"><p>{heading}</p>'
            f'{"<span>" + summary + "</span>" if summary else ""}</div>'
            f'<ol class="toc-entries">{"".join(chapter_items)}</ol>'
            '</li>'
        )

    (BOOK / "index.html").write_text(
        f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Contents | Advances in Financial Machine Learning</title>
    <link rel="stylesheet" href="../assets/afml-book.css?v={ASSET_VERSION}">
    <script defer src="../assets/afml-book.js?v={ASSET_VERSION}"></script>
  </head>
  <body>
    <header class="book-topbar">
      <div>
        <a class="book-title" href="index.html">Advances in Financial Machine Learning</a>
        <span>Contents</span>
      </div>
      <nav aria-label="Book navigation">
        <a href="front-matter.html">Front Matter</a>
        <a href="chapter-01.html">Start Reading</a>
      </nav>
    </header>
    <main class="content contents-home">
      <article>
        <header class="contents-hero">
          <p>Marcos López de Prado</p>
          <h1>Advances in Financial Machine Learning</h1>
          <div class="contents-actions">
            <a href="chapter-01.html">Start with Chapter 1</a>
            <a href="front-matter.html">Open Front Matter</a>
          </div>
        </header>
        <div class="contents-body">
          <aside class="contents-sidebar">
            <section class="toc-tools" aria-label="Contents tools">
              <label for="toc-search">Search contents</label>
              <input id="toc-search" class="toc-search" type="search" placeholder="Search chapters, parts, topics" autocomplete="off">
            </section>
            <div class="contents-note">
              <p>Static web edition</p>
              <span>Chapter pages stay focused on reading; this page provides the full book navigation.</span>
            </div>
          </aside>
          <nav class="book-toc-panel" aria-label="Table of contents">
            <h2>Table of contents</h2>
            <ol class="book-toc-list" data-toc-grid>
              {''.join(part_items)}
            </ol>
          </nav>
        </div>
      </article>
    </main>
  </body>
</html>
""",
        encoding="utf-8",
    )


def write_css() -> None:
    ASSET_CSS.write_text(
        """* { box-sizing: border-box; }
:root {
  color-scheme: dark;
  --bg: #0f1318;
  --ink: #f1f5f9;
  --text: #d6dde5;
  --muted: #9aa6b2;
  --line: #2a333d;
  --link: #8fb4ff;
  --code: #171d24;
  --code-line: #38424d;
  --panel: #151b22;
  --panel-strong: #1d2530;
  --table-stripe: #131920;
  --focus: #496a9f;
}
:root[data-theme="light"] {
  color-scheme: light;
  --bg: #ffffff;
  --ink: #444444;
  --text: #575757;
  --muted: #777777;
  --line: #eeeeee;
  --link: #304080;
  --code: #f8f8f8;
  --code-line: #dddddd;
  --panel: #fbfbfb;
  --panel-strong: #f7f8fc;
  --table-stripe: #fbfbfb;
  --focus: #c9d0e6;
}
html, body { min-height: 100%; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  font-size: 16px;
  line-height: 1.55;
  letter-spacing: 0;
  text-rendering: optimizeLegibility;
}
a { color: var(--link); text-decoration: none; }
a:hover { text-decoration: underline; }
article a { overflow-wrap: anywhere; }
.book-topbar {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 1rem;
  max-width: 72rem;
  margin: 0 auto;
  padding: .9rem 1.25rem .75rem;
  color: var(--muted);
  font-size: .9rem;
}
.book-topbar div {
  min-width: 0;
}
.book-title {
  display: inline-block;
  margin-right: .65rem;
  color: var(--ink);
  font-weight: 600;
}
.book-topbar span {
  color: var(--muted);
}
.book-topbar nav {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  align-items: center;
  gap: .7rem;
  white-space: nowrap;
}
.theme-toggle,
.notes-toggle {
  display: inline-flex;
  align-items: center;
  gap: .42rem;
  min-height: 1.9rem;
  border: 1px solid var(--code-line);
  border-radius: 999px;
  padding: .18rem .58rem .18rem .32rem;
  background: var(--panel);
  color: var(--ink);
  font: 600 .82rem/1.35 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  cursor: pointer;
}
.theme-toggle::before,
.notes-toggle::before {
  content: "";
  width: .72rem;
  height: .72rem;
  border-radius: 50%;
  background: var(--link);
}
.notes-toggle::before {
  width: .62rem;
  height: .82rem;
  border-radius: 2px;
}
.notes-toggle.has-notes::after {
  content: "";
  width: .42rem;
  height: .42rem;
  border-radius: 50%;
  background: var(--link);
}
.theme-toggle:hover,
.notes-toggle:hover {
  border-color: var(--link);
}
.theme-toggle:focus-visible,
.notes-toggle:focus-visible,
.reader-notes-close:focus-visible,
.reader-notes-command:focus-visible,
.codex-selection-button:focus-visible,
.codex-selection-close:focus-visible,
.codex-selection-command:focus-visible,
.codex-selection-question:focus {
  outline: 2px solid var(--focus);
  outline-offset: 2px;
}
.reader-notes-panel {
  position: fixed;
  top: 4.25rem;
  right: 1rem;
  bottom: 1rem;
  z-index: 20;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  width: min(28rem, calc(100vw - 2rem));
  border: 1px solid var(--code-line);
  border-radius: 6px;
  background: var(--panel);
  color: var(--text);
  box-shadow: 0 1rem 2rem rgba(0, 0, 0, .24);
  overflow: hidden;
}
.reader-notes-panel[hidden] {
  display: none;
}
.reader-notes-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: .75rem;
  border-bottom: 1px solid var(--line);
  padding: .85rem 1rem;
}
.reader-notes-title {
  margin: 0;
  color: var(--ink);
  font-size: 1rem;
  font-weight: 700;
}
.reader-notes-status {
  margin-left: auto;
  color: var(--muted);
  font-size: .78rem;
  white-space: nowrap;
}
.reader-notes-close {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.8rem;
  height: 1.8rem;
  border: 1px solid var(--code-line);
  border-radius: 4px;
  background: var(--panel-strong);
  color: var(--ink);
  font: 700 .95rem/1 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  cursor: pointer;
}
.reader-notes-body {
  min-height: 0;
  overflow-y: auto;
  padding: 1rem;
}
.reader-notes-label,
.reader-notes-list-title {
  display: block;
  margin: 0 0 .45rem;
  color: var(--ink);
  font-size: .86rem;
  font-weight: 700;
}
.reader-notes-textarea {
  display: block;
  width: 100%;
  min-height: 14rem;
  resize: vertical;
  border: 1px solid var(--code-line);
  border-radius: 4px;
  padding: .75rem .85rem;
  background: var(--bg);
  color: var(--text);
  font: 1rem/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
}
.reader-notes-textarea:focus {
  outline: 2px solid var(--focus);
  outline-offset: 1px;
  border-color: var(--link);
}
.reader-notes-actions {
  display: flex;
  flex-wrap: wrap;
  gap: .5rem;
  margin: .75rem 0 1rem;
}
.reader-notes-command {
  min-height: 2rem;
  border: 1px solid var(--code-line);
  border-radius: 4px;
  padding: .32rem .65rem;
  background: var(--panel-strong);
  color: var(--ink);
  font: 650 .82rem/1.35 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  cursor: pointer;
}
.reader-notes-command:hover {
  border-color: var(--link);
  color: var(--link);
}
.reader-notes-list {
  display: grid;
  gap: .65rem;
  margin-top: .45rem;
}
.reader-notes-empty {
  margin: 0;
  color: var(--muted);
  font-size: .88rem;
}
.reader-notes-entry {
  border-top: 1px solid var(--line);
  padding-top: .65rem;
}
.reader-notes-entry a {
  color: var(--ink);
  font-size: .88rem;
  font-weight: 700;
}
.reader-notes-entry time {
  display: block;
  margin-top: .15rem;
  color: var(--muted);
  font-size: .76rem;
}
.reader-notes-entry p {
  margin: .35rem 0 0;
  color: var(--muted);
  font-size: .84rem;
  line-height: 1.42;
}
.codex-selection-button {
  position: fixed;
  z-index: 35;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 2rem;
  border: 1px solid var(--focus);
  border-radius: 999px;
  padding: .34rem .72rem;
  background: var(--panel-strong);
  color: var(--ink);
  box-shadow: 0 .65rem 1.35rem rgba(0, 0, 0, .24);
  font: 700 .82rem/1.2 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  cursor: pointer;
}
.codex-selection-button:hover {
  border-color: var(--link);
  color: var(--link);
}
.codex-selection-button[hidden] {
  display: none;
}
.codex-selection-dialog {
  position: fixed;
  top: 4.25rem;
  right: 1rem;
  z-index: 40;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  width: min(30rem, calc(100vw - 2rem));
  max-height: min(42rem, calc(100vh - 5.25rem));
  border: 1px solid var(--code-line);
  border-radius: 6px;
  background: var(--panel);
  color: var(--text);
  box-shadow: 0 1rem 2rem rgba(0, 0, 0, .26);
  overflow: hidden;
}
.codex-selection-dialog[hidden] {
  display: none;
}
.codex-selection-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: .75rem;
  border-bottom: 1px solid var(--line);
  padding: .85rem 1rem;
}
.codex-selection-title {
  margin: 0;
  color: var(--ink);
  font-size: 1rem;
  font-weight: 700;
}
.codex-selection-close {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.8rem;
  height: 1.8rem;
  border: 1px solid var(--code-line);
  border-radius: 4px;
  background: var(--panel-strong);
  color: var(--ink);
  font: 700 .95rem/1 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  cursor: pointer;
}
.codex-selection-body {
  min-height: 0;
  overflow-y: auto;
  padding: 1rem;
}
.codex-selection-label {
  display: block;
  margin: 0 0 .45rem;
  color: var(--ink);
  font-size: .86rem;
  font-weight: 700;
}
.codex-selection-excerpt {
  max-height: 8rem;
  overflow: auto;
  margin: 0 0 .9rem;
  border-left: 3px solid var(--focus);
  padding: .65rem .75rem;
  background: var(--bg);
  color: var(--muted);
  font-size: .86rem;
  line-height: 1.55;
  white-space: pre-wrap;
}
.codex-selection-question {
  display: block;
  width: 100%;
  min-height: 7.5rem;
  resize: vertical;
  border: 1px solid var(--code-line);
  border-radius: 4px;
  padding: .75rem .85rem;
  background: var(--bg);
  color: var(--text);
  font: 1rem/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
}
.codex-selection-question:focus {
  border-color: var(--link);
}
.codex-selection-actions {
  display: flex;
  flex-wrap: wrap;
  gap: .5rem;
  margin-top: .75rem;
}
.codex-selection-command {
  min-height: 2rem;
  border: 1px solid var(--code-line);
  border-radius: 4px;
  padding: .32rem .65rem;
  background: var(--panel-strong);
  color: var(--ink);
  font: 650 .82rem/1.35 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  cursor: pointer;
}
.codex-selection-command.primary {
  border-color: var(--focus);
  color: var(--link);
}
.codex-selection-command:hover {
  border-color: var(--link);
  color: var(--link);
}
.codex-selection-status {
  display: block;
  min-height: 1.25rem;
  margin-top: .65rem;
  color: var(--muted);
  font-size: .8rem;
  line-height: 1.4;
}
.selection-note-highlight {
  border-radius: 3px;
  background: rgba(250, 204, 21, .34);
  box-shadow: inset 0 -.18em 0 rgba(245, 158, 11, .52);
  cursor: pointer;
}
:root[data-theme="dark"] .selection-note-highlight {
  background: rgba(250, 204, 21, .24);
  box-shadow: inset 0 -.18em 0 rgba(251, 191, 36, .48);
}
.selection-note-highlight:hover,
.selection-note-highlight:focus {
  outline: 2px solid var(--focus);
  outline-offset: 1px;
  background: rgba(250, 204, 21, .46);
}
:root[data-theme="dark"] .selection-note-highlight:hover,
:root[data-theme="dark"] .selection-note-highlight:focus {
  background: rgba(250, 204, 21, .34);
}
.book-layout {
  display: block;
  min-height: 100vh;
}
.content {
  min-width: 0;
  padding: .25rem 1.25rem 4rem;
}
article {
  max-width: 68rem;
  min-width: 0;
  margin: 0 auto;
  overflow-x: clip;
}
.chapter-header {
  margin: .3rem 0 1.6rem;
  padding-bottom: .75rem;
  border-bottom: 1px solid var(--line);
}
.chapter-header p {
  margin: 0 0 .35rem;
  color: var(--muted);
  font-size: .9rem;
}
.contents-home article {
  max-width: 74rem;
}
.contents-hero {
  margin: .4rem 0 1.6rem;
  padding-bottom: 1.4rem;
  border-bottom: 1px solid var(--line);
}
.contents-hero p {
  margin: 0 0 .35rem;
  color: var(--muted);
  font-size: .92rem;
}
.contents-hero h1 {
  max-width: 48rem;
}
.contents-actions {
  display: flex;
  flex-wrap: wrap;
  gap: .65rem;
  margin-top: 1.05rem;
}
.contents-actions a {
  display: inline-flex;
  align-items: center;
  min-height: 2.15rem;
  border: 1px solid var(--line);
  border-radius: 4px;
  padding: .35rem .75rem;
  color: var(--ink);
  font-size: .9rem;
  font-weight: 600;
  background: var(--panel);
}
.contents-actions a:first-child {
  border-color: var(--focus);
  color: var(--link);
  background: var(--panel-strong);
}
.contents-body {
  display: grid;
  grid-template-columns: minmax(13rem, 17rem) minmax(0, 1fr);
  gap: 2rem;
  align-items: start;
}
.contents-sidebar {
  position: sticky;
  top: 1rem;
  display: grid;
  gap: 1rem;
}
.toc-tools {
  display: grid;
  gap: .35rem;
}
.toc-tools label {
  color: var(--muted);
  font-size: .85rem;
  font-weight: 600;
}
.toc-search {
  width: 100%;
  border: 1px solid var(--code-line);
  border-radius: 4px;
  padding: .55rem .7rem;
  color: var(--ink);
  font: inherit;
  font-size: .95rem;
  background: var(--panel);
}
.toc-search:focus {
  outline: 2px solid var(--focus);
  outline-offset: 1px;
  border-color: var(--link);
}
.contents-note {
  border-left: 3px solid var(--focus);
  padding-left: .8rem;
  color: var(--muted);
}
.contents-note p {
  margin: 0 0 .2rem;
  color: var(--ink);
  font-size: .88rem;
  font-weight: 700;
  line-height: 1.35;
}
.contents-note span {
  display: block;
  font-size: .82rem;
  line-height: 1.45;
}
.book-toc-panel {
  min-width: 0;
}
.book-toc-panel h2 {
  margin-top: 0;
  padding-bottom: .55rem;
  border-bottom: 1px solid var(--line);
  font-size: 1.25rem;
}
.book-toc-list,
.toc-entries,
.toc-sections {
  margin: 0;
  padding: 0;
  list-style: none;
}
.book-toc-list {
  display: grid;
  gap: 1.15rem;
}
.toc-part {
  display: grid;
  grid-template-columns: minmax(10rem, 15rem) minmax(0, 1fr);
  gap: 1.35rem;
  border-top: 1px solid var(--line);
  padding-top: 1rem;
}
.toc-part:first-child {
  border-top: 0;
  padding-top: 0;
}
.toc-part[hidden] {
  display: none;
}
.toc-part-heading p {
  margin: 0 0 .35rem;
  color: var(--ink);
  font-size: .95rem;
  font-weight: 700;
  line-height: 1.35;
}
.toc-part-heading span {
  display: block;
  color: var(--muted);
  font-size: .82rem;
  line-height: 1.45;
}
.toc-entries {
  display: grid;
  gap: .05rem;
}
.toc-chapter {
  min-width: 0;
  border-bottom: 1px solid var(--line);
  padding: .38rem 0 .45rem;
}
.toc-chapter[hidden] {
  display: none;
}
.toc-entry {
  display: grid;
  grid-template-columns: 2.35rem minmax(0, 1fr);
  align-items: baseline;
  color: var(--ink);
}
.toc-entry:hover {
  color: var(--link);
  text-decoration: none;
}
.toc-number {
  color: var(--link);
  font-size: .82rem;
  font-weight: 700;
}
.toc-number-muted {
  color: var(--muted);
}
.toc-entry span:last-child {
  min-width: 0;
  font-size: .95rem;
  line-height: 1.35;
  overflow-wrap: anywhere;
}
.toc-details {
  margin: .25rem 0 0 2.35rem;
}
.toc-details summary {
  width: fit-content;
  color: var(--muted);
  font-size: .78rem;
  line-height: 1.35;
  cursor: pointer;
}
.toc-details summary:hover {
  color: var(--link);
}
.toc-sections {
  display: grid;
  gap: .16rem;
  margin-top: .35rem;
}
.toc-sections li {
  margin: 0;
  min-width: 0;
}
.toc-sections a {
  display: block;
  color: var(--muted);
  font-size: .82rem;
  line-height: 1.35;
  overflow-wrap: anywhere;
}
.toc-sections a:hover {
  color: var(--link);
}
.toc-section-level-3 {
  padding-left: .8rem;
}
.toc-section-level-3 a {
  color: var(--muted);
  font-size: .78rem;
}
.chapter-authors {
  color: var(--muted);
  font-size: .95rem;
  margin-top: -0.6rem;
}
h1, h2, h3, h4 {
  color: var(--ink);
  font-weight: 500;
  line-height: 1.2;
}
h1 { margin: 0; font-size: 2rem; }
h2 { margin: 2rem 0 1rem; font-size: 1.5rem; }
h3 { margin: 1.5rem 0 .8rem; font-size: 1.2rem; }
h4 { margin: 1.5rem 0 .65rem; font-size: 1.1rem; }
p, li {
  font-size: 1rem;
  line-height: 1.58;
}
p, ul, ol, table, figure, .math.display, .formula {
  margin-top: 0;
  margin-bottom: 1rem;
}
ul, ol { padding-left: 2rem; }
main li + li { margin-top: .18rem; }
.algorithm-list ol { margin: .35rem 0 .45rem; }
.example-caption {
  color: var(--muted);
  font-size: .9rem;
}
.footnote {
  color: var(--muted);
  font-size: .9rem;
  overflow-wrap: anywhere;
}
.faq-question {
  margin-top: 1.25rem;
  margin-bottom: .35rem;
  color: var(--ink);
}
.faq-question + p {
  margin-top: 0;
}
.citation {
  color: var(--text);
  font-size: .95em;
  white-space: nowrap;
}
.references-heading {
  margin-top: 2.5rem;
  padding-top: 1rem;
  border-top: 1px solid var(--line);
}
.references-heading ~ p {
  color: var(--muted);
  font-size: .92rem;
  line-height: 1.5;
  margin-bottom: .65rem;
}
.references-list {
  margin: 0 0 1.25rem;
  padding-left: 0;
  color: var(--muted);
  list-style: none;
}
.references-list li {
  font-size: .88rem;
  line-height: 1.45;
  margin-bottom: .5rem;
  padding-left: 1.5rem;
  text-indent: -1.5rem;
  overflow-wrap: anywhere;
}
figcaption, caption {
  color: var(--muted);
  font-size: .9rem;
  line-height: 1.45;
}
.book-figure figcaption,
figure.table-figure figcaption {
  display: block;
  margin-top: .85rem;
  margin-left: 0;
  margin-right: 0;
  padding-top: .55rem;
  border-top: 1px solid var(--line);
  max-width: 52rem;
  color: var(--muted);
  font-size: .82rem;
  line-height: 1.4;
  text-align: left;
  overflow-wrap: anywhere;
}
.book-figure figcaption .math.inline,
figure.table-figure figcaption .math.inline {
  font-size: 1em;
  vertical-align: baseline;
}
.book-figure figcaption mjx-container,
figure.table-figure figcaption mjx-container {
  font-size: 100% !important;
}
figure.table-figure figcaption {
  margin-top: 0;
  margin-bottom: .55rem;
}
.book-figure {
  border-top: 2px solid var(--line);
  border-bottom: 2px solid var(--line);
  margin: 1.5rem 0 1rem;
  padding: 1.25rem .75rem .85rem;
}
.figure-panels {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
  align-items: end;
}
.figure-panel {
  display: grid;
  gap: .35rem;
  justify-items: center;
}
.panel-label {
  color: var(--muted);
  font-size: .78rem;
  line-height: 1;
}
.book-figure img {
  display: block;
  max-width: 100%;
  height: auto;
  margin: 0 auto .5rem;
}
.book-cover {
  margin: 0 0 1.5rem;
}
.book-cover img {
  display: block;
  max-width: min(100%, 28rem);
  height: auto;
  margin: 0 auto;
}
pre {
  margin: 0;
  overflow-x: auto;
  white-space: pre;
}
code, pre {
  font-family: SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
  font-size: .875rem;
  line-height: 1.5;
}
code {
  padding: .12rem .25rem;
  background: var(--code);
  overflow-wrap: anywhere;
  word-break: break-word;
}
pre code {
  padding: 0;
  background: transparent;
}
.sourceCode { overflow: visible; }
div.sourceCode {
  overflow-x: auto;
  overflow-y: hidden;
  max-width: 100%;
  box-sizing: border-box;
  contain: layout paint;
  background: var(--code);
  border: 1px solid var(--code-line);
  border-radius: 2px;
}
pre.sourceCode {
  width: max-content;
  min-width: 100%;
  max-width: 100%;
  margin: 0;
  padding: 1rem 1.15rem;
  box-sizing: border-box;
}
code.sourceCode {
  display: block;
  width: max-content;
  min-width: 100%;
  white-space: pre;
  background: transparent;
  overflow-wrap: normal;
  word-break: normal;
}
figure.code-listing {
  position: relative;
  width: 100%;
  max-width: 100%;
  margin-left: 0;
  margin-right: 0;
  box-sizing: border-box;
  overflow-x: hidden;
  overflow-y: visible;
}
figure.code-listing figcaption {
  margin: 0 4.5rem .3rem 0;
  color: var(--muted);
  font-weight: 600;
}
.quote-snippet {
  padding: 1rem 1.15rem;
  border: 1px solid var(--code-line);
  border-left: 4px solid var(--focus);
  background: var(--panel);
}
.quote-snippet figcaption {
  margin-bottom: .65rem;
  color: var(--muted);
  font-size: .9rem;
  font-weight: 600;
}
.quote-snippet blockquote {
  margin: 0;
}
.quote-snippet p {
  margin: 0;
}
.quote-snippet blockquote p {
  color: var(--text);
  font-family: Georgia, "Times New Roman", serif;
  font-size: 1.05rem;
  line-height: 1.55;
}
.quote-attribution {
  margin-top: .65rem !important;
  color: var(--muted);
  font-size: .9rem;
  text-align: right;
}
figure.table-figure {
  margin-left: 0;
  margin-right: 0;
}
.cpcv-figure figcaption {
  margin-bottom: .55rem;
  color: var(--muted);
  font-size: .82rem;
  line-height: 1.4;
}
.cpcv-table {
  min-width: 58rem;
  table-layout: fixed;
}
.cpcv-table th,
.cpcv-table td {
  padding: .32rem .38rem;
  text-align: center;
  white-space: nowrap;
}
.cpcv-table th:first-child {
  width: 4rem;
}
.cpcv-table th:last-child,
.cpcv-table td:last-child {
  width: 4.25rem;
  font-weight: 600;
}
.copy-code {
  position: absolute;
  top: 0;
  right: 0;
  border: 1px solid var(--code-line);
  border-radius: 3px;
  padding: .18rem .55rem;
  background: var(--panel);
  color: var(--muted);
  font: 600 .78rem/1.4 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  cursor: pointer;
}
.copy-code:hover {
  color: var(--link);
  border-color: var(--link);
}
code span.cn { color: #ff9b9b; }
code span.co { color: #8db3c7; font-style: italic; }
code span.dv { color: #8ee3a1; }
code span.fu { color: #9fc7ff; }
code span.kw { color: #7dd3fc; font-weight: 700; }
code span.op { color: #c8d0d8; }
code span.st { color: #f0c674; }
code span.va { color: #c4b5fd; }
.formula {
  padding: .85rem 1rem;
  background: var(--code);
  border: 1px solid var(--code-line);
  border-radius: 2px;
}
.math.display {
  max-width: 100%;
  overflow-x: hidden;
  overflow-y: hidden;
  contain: layout paint;
  padding: .25rem 0;
  text-align: center;
}
.math.inline {
  display: inline-block;
  max-width: 100%;
  overflow-x: auto;
  overflow-y: hidden;
  white-space: nowrap;
  vertical-align: middle;
}
.math.display mjx-container[jax="SVG"] {
  display: block;
  width: 100%;
  max-width: 100%;
  overflow-x: auto;
  overflow-y: hidden;
  contain: layout paint;
  padding-bottom: .1rem;
}
.math.display mjx-container[jax="SVG"] > svg {
  overflow: hidden;
}
.math.inline mjx-container[jax="SVG"] {
  max-width: 100%;
  overflow-x: auto;
  overflow-y: hidden;
  vertical-align: middle;
}
.math.inline mjx-container[jax="SVG"] > svg {
  overflow: hidden;
}
.formula pre {
  font-family: "STIX Two Math", "Cambria Math", "Times New Roman", serif;
  font-size: 1rem;
  line-height: 1.5;
}
.table-wrap {
  overflow-x: auto;
  border: 1px solid var(--code-line);
}
table {
  width: 100%;
  border-collapse: collapse;
  font-size: .92rem;
  line-height: 1.42;
}
th, td {
  border: 1px solid var(--code-line);
  padding: .45rem .6rem;
  text-align: left;
  vertical-align: top;
}
th { background: var(--panel-strong); font-weight: 700; }
tr:nth-child(even) td { background: var(--table-stripe); }
.semantic-table ul {
  margin: 0;
  padding-left: 1.15rem;
}
.semantic-table li {
  font-size: .9rem;
  line-height: 1.45;
}
.semantic-table li + li { margin-top: .08rem; }
.pdf-page-anchor {
  display: block;
  height: 0;
  scroll-margin-top: 1rem;
}
.chapter-pager {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  margin-top: 2.4rem;
  border-top: 1px solid var(--line);
  padding-top: 1rem;
}
.chapter-pager a {
  font-size: .95rem;
  font-weight: 600;
}
@media (min-width: 1200px) {
  body { font-size: 18px; }
}
@media (max-width: 760px) {
  .book-topbar {
    display: block;
    padding: .85rem 1rem .35rem;
  }
  .book-topbar nav {
    justify-content: flex-start;
    margin-top: .35rem;
  }
  .reader-notes-panel {
    top: 5rem;
    right: .75rem;
    bottom: .75rem;
    left: .75rem;
    width: auto;
  }
  .codex-selection-dialog {
    top: 5rem;
    right: .75rem;
    left: .75rem;
    width: auto;
    max-height: calc(100vh - 5.75rem);
  }
  .content { padding: .5rem 1rem 3rem; }
  .contents-actions {
    display: grid;
  }
  .contents-actions a {
    justify-content: center;
  }
  .contents-body {
    grid-template-columns: 1fr;
    gap: 1.25rem;
  }
  .contents-sidebar {
    position: static;
  }
  .toc-part {
    grid-template-columns: 1fr;
    gap: .65rem;
  }
  .book-figure {
    padding-left: 1rem;
    padding-right: 1rem;
  }
  .figure-panels {
    grid-template-columns: 1fr;
  }
  h1 { font-size: 1.75rem; }
}
""",
        encoding="utf-8",
    )


def write_js() -> None:
    ASSET_JS.write_text(
        """const THEME_STORAGE_KEY = "afml-theme";
const THEME_DARK = "dark";
const THEME_LIGHT = "light";
let activeTheme = THEME_DARK;

const safeReadTheme = () => {
  try {
    return localStorage.getItem(THEME_STORAGE_KEY);
  } catch {
    return null;
  }
};

const safeWriteTheme = theme => {
  try {
    localStorage.setItem(THEME_STORAGE_KEY, theme);
  } catch {
    // Ignore storage failures; the button still works for this page view.
  }
};

const themeLabels = () => {
  const isZh = document.documentElement.lang.toLowerCase().startsWith("zh");
  return {
    dark: isZh ? "深色" : "Dark",
    light: isZh ? "浅色" : "Light",
    label: isZh ? "切换深色/浅色模式" : "Toggle light and dark mode",
  };
};

const updateThemeToggle = button => {
  if (!button) return;
  const labels = themeLabels();
  button.textContent = activeTheme === THEME_DARK ? labels.dark : labels.light;
  button.setAttribute("aria-label", labels.label);
  button.setAttribute("aria-checked", String(activeTheme === THEME_DARK));
};

const applyTheme = theme => {
  activeTheme = theme === THEME_LIGHT ? THEME_LIGHT : THEME_DARK;
  document.documentElement.dataset.theme = activeTheme;
  updateThemeToggle(document.querySelector(".theme-toggle"));
};

applyTheme(safeReadTheme());

const installThemeToggle = () => {
  const nav = document.querySelector(".book-topbar nav");
  if (!nav || nav.querySelector(".theme-toggle")) return;
  const button = document.createElement("button");
  button.className = "theme-toggle";
  button.type = "button";
  button.setAttribute("role", "switch");
  button.addEventListener("click", () => {
    const nextTheme = activeTheme === THEME_DARK ? THEME_LIGHT : THEME_DARK;
    applyTheme(nextTheme);
    safeWriteTheme(nextTheme);
  });
  nav.appendChild(button);
  updateThemeToggle(button);
};

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", installThemeToggle);
} else {
  installThemeToggle();
}

const NOTES_STORAGE_KEY = "afml-reader-notes";
const NOTES_SAVE_DELAY_MS = 450;
let notesSaveTimer = 0;

const noteLabels = () => {
  const isZh = document.documentElement.lang.toLowerCase().startsWith("zh");
  return {
    locale: isZh ? "zh-CN" : "en",
    open: isZh ? "笔记" : "Notes",
    openLabel: isZh ? "打开读书笔记" : "Open reading notes",
    panel: isZh ? "读书笔记" : "Reading Notes",
    close: isZh ? "关闭" : "Close",
    current: isZh ? "本章笔记" : "Chapter note",
    savedNotes: isZh ? "已保存笔记" : "Saved notes",
    noNotes: isZh ? "暂无笔记" : "No notes yet",
    emptyStatus: isZh ? "未保存" : "Not saved",
    saving: isZh ? "保存中" : "Saving",
    saved: isZh ? "已保存" : "Saved",
    failed: isZh ? "无法保存" : "Unable to save",
    copy: isZh ? "复制" : "Copy",
    copied: isZh ? "已复制" : "Copied",
    export: isZh ? "导出" : "Export",
    clear: isZh ? "清空" : "Clear",
    cleared: isZh ? "已清空" : "Cleared",
    clearConfirm: isZh ? "清空本章笔记？" : "Clear this chapter note?",
    exportTitle: isZh ? "AFML 读书笔记" : "AFML Reading Notes",
    page: isZh ? "页面" : "Page",
    updated: isZh ? "更新" : "Updated",
    untitled: isZh ? "本页" : "Untitled page",
  };
};

const notePageKey = () => location.pathname.replace(/\\/$/, "/index.html");

const readNotesStore = () => {
  try {
    const parsed = JSON.parse(localStorage.getItem(NOTES_STORAGE_KEY) || "{}");
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {};
  } catch {
    return {};
  }
};

const writeNotesStore = notes => {
  try {
    localStorage.setItem(NOTES_STORAGE_KEY, JSON.stringify(notes));
    return true;
  } catch {
    return false;
  }
};

const currentNoteTitle = labels => {
  const heading = document.querySelector("h1");
  return (heading && heading.textContent.trim()) || document.title || labels.untitled;
};

const formatNoteTime = (iso, labels) => {
  if (!iso) return "";
  try {
    return new Intl.DateTimeFormat(labels.locale, {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
};

const writeClipboardText = async text => {
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.setAttribute("readonly", "");
    textarea.style.position = "fixed";
    textarea.style.left = "-9999px";
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand("copy");
    textarea.remove();
  }
};

const noteStoreEntries = notes => Object.values(notes)
  .filter(note => note && typeof note.text === "string" && note.text.trim())
  .sort((left, right) => (right.updatedAt || "").localeCompare(left.updatedAt || ""));

const notesToMarkdown = (notes, labels) => {
  const entries = noteStoreEntries(notes);
  const chunks = [`# ${labels.exportTitle}`];
  for (const note of entries) {
    chunks.push([
      `## ${note.title || labels.untitled}`,
      "",
      `- ${labels.page}: ${note.url || ""}`,
      `- ${labels.updated}: ${formatNoteTime(note.updatedAt, labels)}`,
      "",
      note.text.trim(),
    ].join("\\n"));
  }
  return `${chunks.join("\\n\\n")}\\n`;
};

const renderNotesList = (container, labels) => {
  const entries = noteStoreEntries(readNotesStore());
  container.textContent = "";
  if (!entries.length) {
    const empty = document.createElement("p");
    empty.className = "reader-notes-empty";
    empty.textContent = labels.noNotes;
    container.appendChild(empty);
    return;
  }
  for (const note of entries) {
    const item = document.createElement("article");
    item.className = "reader-notes-entry";
    const link = document.createElement("a");
    link.href = note.url || "#";
    link.textContent = note.title || labels.untitled;
    const time = document.createElement("time");
    if (note.updatedAt) time.dateTime = note.updatedAt;
    time.textContent = formatNoteTime(note.updatedAt, labels);
    const excerpt = document.createElement("p");
    excerpt.textContent = note.text.trim().replace(/\\s+/g, " ").slice(0, 140);
    item.append(link, time, excerpt);
    container.appendChild(item);
  }
};

const installReaderNotes = () => {
  const nav = document.querySelector(".book-topbar nav");
  if (!nav || nav.querySelector("[data-reader-notes='toggle']")) return;
  const labels = noteLabels();
  const pageKey = notePageKey();

  const toggle = document.createElement("button");
  toggle.className = "notes-toggle";
  toggle.type = "button";
  toggle.dataset.readerNotes = "toggle";
  toggle.textContent = labels.open;
  toggle.setAttribute("aria-label", labels.openLabel);
  toggle.setAttribute("aria-expanded", "false");
  nav.appendChild(toggle);

  const panel = document.createElement("aside");
  panel.className = "reader-notes-panel";
  panel.dataset.readerNotes = "panel";
  panel.hidden = true;
  panel.setAttribute("aria-label", labels.panel);

  const header = document.createElement("div");
  header.className = "reader-notes-header";
  const title = document.createElement("h2");
  title.className = "reader-notes-title";
  title.textContent = labels.panel;
  const status = document.createElement("span");
  status.className = "reader-notes-status";
  const close = document.createElement("button");
  close.className = "reader-notes-close";
  close.type = "button";
  close.textContent = "x";
  close.setAttribute("aria-label", labels.close);
  header.append(title, status, close);

  const body = document.createElement("div");
  body.className = "reader-notes-body";
  const noteLabel = document.createElement("label");
  noteLabel.className = "reader-notes-label";
  noteLabel.textContent = labels.current;
  const textarea = document.createElement("textarea");
  textarea.className = "reader-notes-textarea";
  textarea.rows = 10;
  textarea.spellcheck = true;
  textarea.setAttribute("aria-label", labels.current);
  noteLabel.appendChild(textarea);

  const actions = document.createElement("div");
  actions.className = "reader-notes-actions";
  const copy = document.createElement("button");
  copy.className = "reader-notes-command";
  copy.type = "button";
  copy.textContent = labels.copy;
  const exportNotes = document.createElement("button");
  exportNotes.className = "reader-notes-command";
  exportNotes.type = "button";
  exportNotes.textContent = labels.export;
  const clear = document.createElement("button");
  clear.className = "reader-notes-command";
  clear.type = "button";
  clear.textContent = labels.clear;
  actions.append(copy, exportNotes, clear);

  const listTitle = document.createElement("h3");
  listTitle.className = "reader-notes-list-title";
  listTitle.textContent = labels.savedNotes;
  const list = document.createElement("div");
  list.className = "reader-notes-list";
  body.append(noteLabel, actions, listTitle, list);
  panel.append(header, body);
  document.body.appendChild(panel);

  const setPanelOpen = open => {
    panel.hidden = !open;
    toggle.setAttribute("aria-expanded", String(open));
    if (open) textarea.focus();
  };

  const updateToggleState = () => {
    toggle.classList.toggle("has-notes", Boolean(textarea.value.trim()));
  };

  const saveCurrentNote = () => {
    const notes = readNotesStore();
    const text = textarea.value.trimEnd();
    if (text.trim()) {
      notes[pageKey] = {
        key: pageKey,
        title: currentNoteTitle(labels),
        url: location.href.split("#")[0],
        text,
        updatedAt: new Date().toISOString(),
      };
    } else {
      delete notes[pageKey];
    }
    status.textContent = writeNotesStore(notes) ? (text.trim() ? labels.saved : labels.emptyStatus) : labels.failed;
    renderNotesList(list, labels);
    updateToggleState();
  };

  const refreshCurrentNote = () => {
    const note = readNotesStore()[pageKey];
    textarea.value = note && typeof note.text === "string" ? note.text : "";
    status.textContent = textarea.value.trim() ? labels.saved : labels.emptyStatus;
    renderNotesList(list, labels);
    updateToggleState();
  };

  textarea.addEventListener("input", () => {
    window.clearTimeout(notesSaveTimer);
    status.textContent = textarea.value.trim() ? labels.saving : labels.emptyStatus;
    notesSaveTimer = window.setTimeout(saveCurrentNote, NOTES_SAVE_DELAY_MS);
    updateToggleState();
  });
  toggle.addEventListener("click", () => setPanelOpen(panel.hidden));
  close.addEventListener("click", () => setPanelOpen(false));
  copy.addEventListener("click", async () => {
    if (!textarea.value.trim()) return;
    const previous = copy.textContent;
    await writeClipboardText(textarea.value);
    copy.textContent = labels.copied;
    window.setTimeout(() => {
      copy.textContent = previous || labels.copy;
    }, 1200);
  });
  exportNotes.addEventListener("click", () => {
    const notes = readNotesStore();
    if (!noteStoreEntries(notes).length) return;
    const blob = new Blob([notesToMarkdown(notes, labels)], { type: "text/markdown;charset=utf-8" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `afml-reading-notes-${new Date().toISOString().slice(0, 10)}.md`;
    document.body.appendChild(link);
    link.click();
    URL.revokeObjectURL(link.href);
    link.remove();
  });
  clear.addEventListener("click", () => {
    if (!textarea.value.trim() || !window.confirm(labels.clearConfirm)) return;
    textarea.value = "";
    saveCurrentNote();
    status.textContent = labels.cleared;
  });
  document.addEventListener("keydown", event => {
    if (event.key === "Escape" && !panel.hidden) setPanelOpen(false);
  });
  window.addEventListener("beforeunload", () => {
    if (notesSaveTimer) {
      window.clearTimeout(notesSaveTimer);
      saveCurrentNote();
    }
  });
  window.addEventListener("storage", event => {
    if (event.key === NOTES_STORAGE_KEY) refreshCurrentNote();
  });
  refreshCurrentNote();
};

// Selection-scoped notes are installed below. The older chapter-wide note panel
// stays unused so existing localStorage data is not destroyed.

const CODEX_SELECTION_LIMIT = 2200;
const CODEX_APP_PROJECT_PATH = "D:/code/github/afml-zh";
const SELECTION_DIALOG_OPEN_EVENT = "afml-selection-dialog-open";
let codexSelectionTimer = 0;

const isGithubPagesHost = hostname => hostname === "github.io" || hostname.endsWith(".github.io");

const codexAppEnabled = () => {
  if (isGithubPagesHost(location.hostname)) return false;
  if (typeof window.AFML_CODEX_APP_ENABLED === "boolean") return window.AFML_CODEX_APP_ENABLED;
  return true;
};

const codexSelectionLabels = () => {
  const isZh = document.documentElement.lang.toLowerCase().startsWith("zh");
  return {
    ask: isZh ? "问 Codex" : "Ask Codex",
    askLabel: isZh ? "用所选文字向 Codex 提问" : "Ask Codex about the selected text",
    panel: isZh ? "问 Codex" : "Ask Codex",
    close: isZh ? "关闭" : "Close",
    selectedText: isZh ? "选中文字" : "Selected text",
    question: isZh ? "问题" : "Question",
    placeholder: isZh ? "你想问这段文字的什么？" : "What do you want to ask about this passage?",
    open: isZh ? "打开 Codex" : "Open Codex",
    copyPrompt: isZh ? "复制提示词" : "Copy prompt",
    copied: isZh ? "已复制提示词" : "Prompt copied",
    opening: isZh ? "已复制提示词，并尝试打开 Codex。" : "Prompt copied. Opening Codex.",
    fallback: isZh ? "如果浏览器没有打开 Codex，请直接粘贴已复制的提示词。" : "If Codex did not open, paste the copied prompt manually.",
    defaultQuestion: isZh ? "请解释这段话，并指出我应该重点理解什么。" : "Please explain this passage and identify what I should understand first.",
    instruction: isZh
      ? "请基于下面《金融机器学习进阶》网页摘录回答我的问题。回答时先解释关键概念，再结合本书上下文说明含义。"
      : "Answer my question using the excerpt below from Advances in Financial Machine Learning. Explain the key concept first, then connect it to the book context.",
    pageTitle: isZh ? "页面标题" : "Page title",
    pageUrl: isZh ? "页面链接" : "Page URL",
    myQuestion: isZh ? "我的问题" : "My question",
    truncated: isZh ? "[选区较长，已截断]" : "[Selection was long and has been truncated]",
  };
};

const cleanSelectedText = text => text
  .replace(/\\r\\n/g, "\\n")
  .replace(/\\n{3,}/g, "\\n\\n")
  .trim();

const elementFromNode = node => {
  if (!node) return null;
  return node.nodeType === Node.ELEMENT_NODE ? node : node.parentElement;
};

const isIgnoredSelectionElement = element => Boolean(element && element.closest(
  "input, textarea, button, nav, .reader-notes-panel, .codex-selection-dialog, .codex-selection-button, .selection-note-dialog, .selection-note-button"
));

const currentPageHeading = labels => {
  const heading = document.querySelector("h1");
  return (heading && heading.textContent.trim()) || document.title || labels.pageTitle;
};

const normalizeSelectionNoteText = text => cleanSelectedText(String(text || "")).replace(/\\s+/g, " ");

const selectionNoteTextNodes = article => {
  const nodes = [];
  const ignoredSelector = [
    "script",
    "style",
    "textarea",
    "input",
    "button",
    "nav",
    "pre",
    "code",
    "mjx-container",
    ".MathJax",
    ".reader-notes-panel",
    ".codex-selection-dialog",
  ].join(",");
  const walker = document.createTreeWalker(article, NodeFilter.SHOW_TEXT, {
    acceptNode(node) {
      const parent = node.parentElement;
      if (!parent || !node.nodeValue || !node.nodeValue.trim()) return NodeFilter.FILTER_REJECT;
      return parent.closest(ignoredSelector) ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT;
    },
  });
  let node = walker.nextNode();
  while (node) {
    nodes.push(node);
    node = walker.nextNode();
  }
  return nodes;
};

const selectionNoteTextIndex = article => {
  const map = [];
  let text = "";
  let sawWhitespace = false;
  for (const node of selectionNoteTextNodes(article)) {
    const value = node.nodeValue || "";
    for (let offset = 0; offset < value.length; offset += 1) {
      const char = value[offset];
      if (/\\s/.test(char)) {
        if (!sawWhitespace) {
          text += " ";
          map.push({ node, offset });
          sawWhitespace = true;
        }
      } else {
        text += char;
        map.push({ node, offset });
        sawWhitespace = false;
      }
    }
  }
  return { text, map };
};

const selectionNoteQuoteIndex = (article, range, quote) => {
  const normalizedQuote = normalizeSelectionNoteText(quote);
  if (!normalizedQuote) return -1;
  const { text } = selectionNoteTextIndex(article);
  const beforeRange = range.cloneRange();
  beforeRange.selectNodeContents(article);
  beforeRange.setEnd(range.startContainer, range.startOffset);
  const beforeLength = normalizeSelectionNoteText(beforeRange.toString()).length;
  const nearbyStart = Math.max(0, beforeLength - 8);
  const nearbyMatch = text.indexOf(normalizedQuote, nearbyStart);
  if (nearbyMatch >= 0 && nearbyMatch <= beforeLength + 8) return nearbyMatch;
  return text.indexOf(normalizedQuote);
};

const codexWorkspacePath = () => {
  const configured = window.AFML_CODEX_PROJECT_PATH || window.AFML_CODEX_WORKSPACE_PATH || CODEX_APP_PROJECT_PATH;
  return typeof configured === "string" ? configured.trim() : "";
};

const selectedArticleText = labels => {
  const selection = window.getSelection();
  if (!selection || selection.isCollapsed || selection.rangeCount === 0) return null;
  const article = document.querySelector("article");
  if (!article) return null;

  const range = selection.getRangeAt(0);
  const startElement = elementFromNode(range.startContainer);
  const endElement = elementFromNode(range.endContainer);
  if (!startElement || !endElement || !article.contains(startElement) || !article.contains(endElement)) return null;
  if (isIgnoredSelectionElement(startElement) || isIgnoredSelectionElement(endElement)) return null;

  const fullText = cleanSelectedText(selection.toString());
  if (fullText.replace(/\\s+/g, "").length < 2) return null;
  const rects = [...range.getClientRects()].filter(rect => rect.width > 0 && rect.height > 0);
  const rect = rects[0] || range.getBoundingClientRect();
  if (!rect || (rect.width === 0 && rect.height === 0)) return null;
  const wasTruncated = fullText.length > CODEX_SELECTION_LIMIT;
  const text = wasTruncated ? fullText.slice(0, CODEX_SELECTION_LIMIT).trimEnd() : fullText;
  const quoteIndex = selectionNoteQuoteIndex(article, range, text);
  return { text, wasTruncated, rect, quoteIndex, title: currentPageHeading(labels), url: location.href.split("#")[0] };
};

const buildCodexPrompt = (selectionData, question, labels) => {
  const excerpt = selectionData.wasTruncated
    ? `${selectionData.text}\\n${labels.truncated}`
    : selectionData.text;
  const promptQuestion = question.trim() || labels.defaultQuestion;
  return [
    labels.instruction,
    "",
    `${labels.pageTitle}: ${selectionData.title}`,
    `${labels.pageUrl}: ${selectionData.url}`,
    "",
    `${labels.selectedText}:`,
    "<<<",
    excerpt,
    ">>>",
    "",
    `${labels.myQuestion}: ${promptQuestion}`,
  ].join("\\n");
};

const codexDeepLinkForPrompt = prompt => {
  const params = new URLSearchParams({ prompt });
  const workspacePath = codexWorkspacePath();
  if (workspacePath) params.set("path", workspacePath);
  return `codex://new?${params.toString()}`;
};

const openCodexLink = href => {
  const link = document.createElement("a");
  link.href = href;
  link.rel = "noreferrer";
  document.body.appendChild(link);
  link.click();
  link.remove();
};

const announceSelectionDialogOpen = panel => {
  document.dispatchEvent(new CustomEvent(SELECTION_DIALOG_OPEN_EVENT, { detail: { panel } }));
};

const positionCodexSelectionButton = (button, rect, slot = 0) => {
  const margin = 8;
  const gap = 8;
  const buttonWidth = button.offsetWidth || 108;
  const buttonHeight = button.offsetHeight || 32;
  const centeredLeft = rect.left + rect.width / 2 - buttonWidth / 2 + slot * (buttonWidth + gap);
  const maxLeft = Math.max(margin, window.innerWidth - buttonWidth - margin);
  const left = Math.min(Math.max(centeredLeft, margin), maxLeft);
  const below = rect.bottom + margin;
  const top = below + buttonHeight + margin <= window.innerHeight
    ? below
    : Math.max(margin, rect.top - buttonHeight - margin);
  button.style.left = `${Math.round(left)}px`;
  button.style.top = `${Math.round(top)}px`;
};

const createCodexSelectionDialog = labels => {
  const panel = document.createElement("aside");
  panel.className = "codex-selection-dialog";
  panel.hidden = true;
  panel.setAttribute("role", "dialog");
  panel.setAttribute("aria-label", labels.panel);

  const header = document.createElement("div");
  header.className = "codex-selection-header";
  const title = document.createElement("h2");
  title.className = "codex-selection-title";
  title.textContent = labels.panel;
  const close = document.createElement("button");
  close.className = "codex-selection-close";
  close.type = "button";
  close.textContent = "x";
  close.setAttribute("aria-label", labels.close);
  header.append(title, close);

  const body = document.createElement("div");
  body.className = "codex-selection-body";
  const excerptLabel = document.createElement("p");
  excerptLabel.className = "codex-selection-label";
  excerptLabel.textContent = labels.selectedText;
  const excerpt = document.createElement("blockquote");
  excerpt.className = "codex-selection-excerpt";

  const questionLabel = document.createElement("label");
  questionLabel.className = "codex-selection-label";
  questionLabel.textContent = labels.question;
  const question = document.createElement("textarea");
  question.className = "codex-selection-question";
  question.rows = 5;
  question.placeholder = labels.placeholder;
  question.spellcheck = true;
  question.setAttribute("aria-label", labels.question);
  questionLabel.appendChild(question);

  const actions = document.createElement("div");
  actions.className = "codex-selection-actions";
  const open = document.createElement("button");
  open.className = "codex-selection-command primary";
  open.type = "button";
  open.textContent = labels.open;
  const copy = document.createElement("button");
  copy.className = "codex-selection-command";
  copy.type = "button";
  copy.textContent = labels.copyPrompt;
  actions.append(open, copy);

  const status = document.createElement("span");
  status.className = "codex-selection-status";
  body.append(excerptLabel, excerpt, questionLabel, actions, status);
  panel.append(header, body);
  document.body.appendChild(panel);
  return { panel, excerpt, question, status, open, copy, close };
};

const installCodexSelectionPrompt = () => {
  if (!codexAppEnabled()) return;
  const article = document.querySelector("article");
  if (!article || document.querySelector("[data-codex-selection='ask']")) return;
  const labels = codexSelectionLabels();
  let selectionData = null;
  let pendingSelectionData = null;

  const button = document.createElement("button");
  button.className = "codex-selection-button";
  button.type = "button";
  button.hidden = true;
  button.setAttribute("data-codex-selection", "ask");
  button.textContent = labels.ask;
  button.setAttribute("aria-label", labels.askLabel);
  document.body.appendChild(button);

  const dialog = createCodexSelectionDialog(labels);

  const hideButton = () => {
    button.hidden = true;
  };

  const refreshSelectionButton = () => {
    pendingSelectionData = selectedArticleText(labels);
    if (!pendingSelectionData) {
      hideButton();
      return;
    }
    button.hidden = false;
    positionCodexSelectionButton(button, pendingSelectionData.rect);
  };

  const scheduleSelectionRefresh = () => {
    window.clearTimeout(codexSelectionTimer);
    codexSelectionTimer = window.setTimeout(refreshSelectionButton, 80);
  };

  const closeDialog = () => {
    dialog.panel.hidden = true;
    dialog.status.textContent = "";
    scheduleSelectionRefresh();
  };

  document.addEventListener(SELECTION_DIALOG_OPEN_EVENT, event => {
    if (event.detail?.panel === dialog.panel) return;
    if (!dialog.panel.hidden) closeDialog();
  });

  const promptFromDialog = () => {
    if (!selectionData) return "";
    return buildCodexPrompt(selectionData, dialog.question.value, labels);
  };

  const copyDialogPrompt = async message => {
    const prompt = promptFromDialog();
    if (!prompt) return;
    await writeClipboardText(prompt);
    dialog.status.textContent = message;
  };

  const openCodexPrompt = async () => {
    const prompt = promptFromDialog();
    if (!prompt) return;
    await writeClipboardText(prompt);
    openCodexLink(codexDeepLinkForPrompt(prompt));
    dialog.status.textContent = labels.opening;
    window.setTimeout(() => {
      if (!dialog.panel.hidden) dialog.status.textContent = labels.fallback;
    }, 1500);
  };

  button.addEventListener("mousedown", event => {
    event.preventDefault();
  });
  button.addEventListener("click", () => {
    selectionData = selectedArticleText(labels) || pendingSelectionData || selectionData;
    if (!selectionData) return;
    pendingSelectionData = null;
    hideButton();
    dialog.excerpt.textContent = selectionData.wasTruncated
      ? `${selectionData.text}\\n${labels.truncated}`
      : selectionData.text;
    dialog.question.value = "";
    dialog.status.textContent = "";
    announceSelectionDialogOpen(dialog.panel);
    dialog.panel.hidden = false;
    dialog.question.focus();
  });
  dialog.close.addEventListener("click", closeDialog);
  dialog.copy.addEventListener("click", () => copyDialogPrompt(labels.copied));
  dialog.open.addEventListener("click", openCodexPrompt);
  dialog.question.addEventListener("keydown", event => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      openCodexPrompt();
    }
  });
  document.addEventListener("selectionchange", scheduleSelectionRefresh);
  document.addEventListener("mouseup", scheduleSelectionRefresh);
  document.addEventListener("touchend", scheduleSelectionRefresh);
  document.addEventListener("keyup", event => {
    if (event.key === "Escape") {
      if (!dialog.panel.hidden) closeDialog();
      hideButton();
      return;
    }
    scheduleSelectionRefresh();
  });
  window.addEventListener("scroll", () => {
    if (!button.hidden) refreshSelectionButton();
  }, { passive: true });
  window.addEventListener("resize", scheduleSelectionRefresh);
};

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", installCodexSelectionPrompt);
} else {
  installCodexSelectionPrompt();
}

const SELECTION_NOTES_STORAGE_KEY = "afml-selection-notes";
const SELECTION_NOTE_SAVE_DELAY_MS = 450;
let selectionNoteTimer = 0;
let selectionNoteSaveTimer = 0;

const selectionNoteLabels = () => {
  const isZh = document.documentElement.lang.toLowerCase().startsWith("zh");
  return {
    locale: isZh ? "zh-CN" : "en",
    add: isZh ? "记笔记" : "Note",
    addLabel: isZh ? "给选中文字添加笔记" : "Add a note to the selected text",
    openSaved: isZh ? "打开这条划词笔记" : "Open this selection note",
    panel: isZh ? "划词笔记" : "Selection Note",
    close: isZh ? "关闭" : "Close",
    selectedText: isZh ? "选中文字" : "Selected text",
    note: isZh ? "笔记" : "Note",
    placeholder: isZh ? "记录你对这段文字的理解、疑问或延伸想法..." : "Record your takeaways, questions, or follow-up thoughts...",
    save: isZh ? "保存" : "Save",
    saving: isZh ? "保存中" : "Saving",
    saved: isZh ? "已保存" : "Saved",
    highlighted: isZh ? "已高亮" : "Highlighted",
    empty: isZh ? "未保存" : "Not saved",
    failed: isZh ? "无法保存" : "Unable to save",
    copyQuote: isZh ? "复制原文" : "Copy quote",
    copied: isZh ? "已复制" : "Copied",
    export: isZh ? "导出全部" : "Export all",
    delete: isZh ? "删除此条" : "Delete",
    deleted: isZh ? "已删除" : "Deleted",
    deleteConfirm: isZh ? "删除这条划词笔记？" : "Delete this selection note?",
    exportTitle: isZh ? "AFML 划词笔记" : "AFML Selection Notes",
    pageUrl: isZh ? "页面链接" : "Page URL",
    quote: isZh ? "原文" : "Quote",
    updated: isZh ? "更新" : "Updated",
    untitled: isZh ? "本页" : "Untitled page",
    none: isZh ? "暂无划词笔记" : "No selection notes yet",
    truncated: isZh ? "[选区较长，已截断]" : "[Selection was long and has been truncated]",
  };
};

const selectionNotesPageKey = () => location.pathname.replace(/\\/$/, "/index.html");

const readSelectionNotes = () => {
  try {
    const parsed = JSON.parse(localStorage.getItem(SELECTION_NOTES_STORAGE_KEY) || "{}");
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {};
  } catch {
    return {};
  }
};

const writeSelectionNotes = notes => {
  try {
    localStorage.setItem(SELECTION_NOTES_STORAGE_KEY, JSON.stringify(notes));
    return true;
  } catch {
    return false;
  }
};

const selectionNoteHash = text => {
  let hash = 2166136261;
  for (const char of text) {
    hash ^= char.codePointAt(0);
    hash = Math.imul(hash, 16777619);
  }
  return (hash >>> 0).toString(36);
};

const selectionNoteEntries = notes => Object.values(notes)
  .filter(note => note && typeof note.note === "string" && note.note.trim())
  .sort((left, right) => (right.updatedAt || "").localeCompare(left.updatedAt || ""));

const formatSelectionNoteTime = (iso, labels) => {
  if (!iso) return "";
  try {
    return new Intl.DateTimeFormat(labels.locale, {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
};

const selectionNotesToMarkdown = (notes, labels) => {
  const nl = String.fromCharCode(10);
  const chunks = [`# ${labels.exportTitle}`];
  for (const note of selectionNoteEntries(notes)) {
    chunks.push([
      `## ${note.title || labels.untitled}`,
      "",
      `- ${labels.pageUrl}: ${note.url || ""}`,
      `- ${labels.updated}: ${formatSelectionNoteTime(note.updatedAt, labels)}`,
      "",
      `${labels.quote}:`,
      "> " + (note.quote || "").split(/\\r?\\n/).join(`${nl}> `),
      "",
      note.note.trim(),
    ].join(nl));
  }
  return `${chunks.join(nl + nl)}${nl}`;
};

const selectionDataForNote = labels => {
  const data = selectedArticleText({ pageTitle: labels.untitled });
  if (!data) return null;
  const pageKey = selectionNotesPageKey();
  return {
    ...data,
    pageKey,
    id: `${pageKey}#${selectionNoteHash(data.text)}`,
  };
};

const pageSelectionNoteEntries = notes => {
  const pageKey = selectionNotesPageKey();
  return Object.values(notes)
    .filter(note => note && note.pageKey === pageKey && note.quote)
    .sort((left, right) => (right.updatedAt || "").localeCompare(left.updatedAt || ""));
};

const clearSelectionNoteHighlights = article => {
  for (const highlight of [...article.querySelectorAll(".selection-note-highlight")]) {
    highlight.replaceWith(document.createTextNode(highlight.textContent || ""));
  }
  article.normalize();
};

const selectionNoteMatchStart = (indexedText, quote, quoteIndex) => {
  const normalizedQuote = normalizeSelectionNoteText(quote);
  if (!normalizedQuote) return -1;
  const preferredIndex = Number.isFinite(quoteIndex) ? Number(quoteIndex) : -1;
  if (preferredIndex >= 0) {
    const exact = indexedText.indexOf(normalizedQuote, preferredIndex);
    if (exact === preferredIndex) return exact;
    const windowStart = Math.max(0, preferredIndex - 120);
    const windowEnd = Math.min(indexedText.length, preferredIndex + normalizedQuote.length + 120);
    const nearby = indexedText.slice(windowStart, windowEnd).indexOf(normalizedQuote);
    if (nearby >= 0) return windowStart + nearby;
  }
  return indexedText.indexOf(normalizedQuote);
};

const selectionNoteSegments = (map, start, length) => {
  const segments = [];
  const end = start + length;
  for (let index = start; index < end; index += 1) {
    const point = map[index];
    if (!point) continue;
    const last = segments[segments.length - 1];
    if (last && last.node === point.node && last.end === point.offset) {
      last.end = point.offset + 1;
    } else {
      segments.push({ node: point.node, start: point.offset, end: point.offset + 1 });
    }
  }
  return segments;
};

const applySelectionNoteHighlight = (article, note, labels) => {
  const normalizedQuote = normalizeSelectionNoteText(note.quote);
  if (!normalizedQuote) return;
  const { text, map } = selectionNoteTextIndex(article);
  const start = selectionNoteMatchStart(text, normalizedQuote, note.quoteIndex);
  if (start < 0) return;
  const segments = selectionNoteSegments(map, start, normalizedQuote.length);
  for (const segment of segments.reverse()) {
    const parent = segment.node.parentNode;
    if (!parent) continue;
    let target = segment.node;
    if (segment.end < target.nodeValue.length) target.splitText(segment.end);
    if (segment.start > 0) target = target.splitText(segment.start);
    const highlight = document.createElement("mark");
    highlight.className = "selection-note-highlight";
    highlight.dataset.selectionNoteId = note.id;
    highlight.tabIndex = 0;
    highlight.setAttribute("role", "button");
    highlight.setAttribute("aria-label", labels.openSaved);
    highlight.title = labels.openSaved;
    target.parentNode.insertBefore(highlight, target);
    highlight.appendChild(target);
  }
};

const refreshSelectionNoteHighlights = labels => {
  const article = document.querySelector("article");
  if (!article) return;
  clearSelectionNoteHighlights(article);
  for (const note of pageSelectionNoteEntries(readSelectionNotes())) {
    applySelectionNoteHighlight(article, note, labels);
  }
};

const createSelectionNoteDialog = labels => {
  const panel = document.createElement("aside");
  panel.className = "codex-selection-dialog selection-note-dialog";
  panel.hidden = true;
  panel.setAttribute("role", "dialog");
  panel.setAttribute("aria-label", labels.panel);

  const header = document.createElement("div");
  header.className = "codex-selection-header";
  const title = document.createElement("h2");
  title.className = "codex-selection-title";
  title.textContent = labels.panel;
  const close = document.createElement("button");
  close.className = "codex-selection-close";
  close.type = "button";
  close.textContent = "x";
  close.setAttribute("aria-label", labels.close);
  header.append(title, close);

  const body = document.createElement("div");
  body.className = "codex-selection-body";
  const excerptLabel = document.createElement("p");
  excerptLabel.className = "codex-selection-label";
  excerptLabel.textContent = labels.selectedText;
  const excerpt = document.createElement("blockquote");
  excerpt.className = "codex-selection-excerpt";

  const noteLabel = document.createElement("label");
  noteLabel.className = "codex-selection-label";
  noteLabel.textContent = labels.note;
  const note = document.createElement("textarea");
  note.className = "codex-selection-question selection-note-textarea";
  note.rows = 6;
  note.placeholder = labels.placeholder;
  note.spellcheck = true;
  note.setAttribute("aria-label", labels.note);
  noteLabel.appendChild(note);

  const actions = document.createElement("div");
  actions.className = "codex-selection-actions";
  const save = document.createElement("button");
  save.className = "codex-selection-command primary";
  save.type = "button";
  save.textContent = labels.save;
  const copyQuote = document.createElement("button");
  copyQuote.className = "codex-selection-command";
  copyQuote.type = "button";
  copyQuote.textContent = labels.copyQuote;
  const exportNotes = document.createElement("button");
  exportNotes.className = "codex-selection-command";
  exportNotes.type = "button";
  exportNotes.textContent = labels.export;
  const remove = document.createElement("button");
  remove.className = "codex-selection-command";
  remove.type = "button";
  remove.textContent = labels.delete;
  actions.append(save, copyQuote, exportNotes, remove);

  const status = document.createElement("span");
  status.className = "codex-selection-status";
  body.append(excerptLabel, excerpt, noteLabel, actions, status);
  panel.append(header, body);
  document.body.appendChild(panel);
  return { panel, excerpt, note, status, save, copyQuote, exportNotes, remove, close };
};

const installSelectionNotes = () => {
  const article = document.querySelector("article");
  if (!article || document.querySelector(".selection-note-button")) return;
  const labels = selectionNoteLabels();
  let selectionData = null;
  let pendingSelectionData = null;

  const button = document.createElement("button");
  button.className = "codex-selection-button selection-note-button";
  button.type = "button";
  button.hidden = true;
  button.textContent = labels.add;
  button.setAttribute("aria-label", labels.addLabel);
  document.body.appendChild(button);

  const dialog = createSelectionNoteDialog(labels);

  const hideButton = () => {
    button.hidden = true;
  };

  const refreshSelectionButton = () => {
    pendingSelectionData = selectionDataForNote(labels);
    if (!pendingSelectionData) {
      hideButton();
      return;
    }
    button.hidden = false;
    positionCodexSelectionButton(button, pendingSelectionData.rect, codexAppEnabled() ? 1 : 0);
  };

  const scheduleSelectionRefresh = () => {
    window.clearTimeout(selectionNoteTimer);
    selectionNoteTimer = window.setTimeout(refreshSelectionButton, 80);
  };

  const selectionNoteRecord = (existing, text) => ({
    id: selectionData.id,
    pageKey: selectionData.pageKey,
    title: selectionData.title,
    url: selectionData.url,
    quote: selectionData.text,
    quoteIndex: Number.isFinite(selectionData.quoteIndex) ? selectionData.quoteIndex : (existing?.quoteIndex ?? null),
    note: text,
    createdAt: existing?.createdAt || new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  });

  const saveCurrentSelectionNote = ({ refreshHighlights = true } = {}) => {
    if (!selectionData?.text) return false;
    const notes = readSelectionNotes();
    const text = dialog.note.value.trimEnd();
    const existing = notes[selectionData.id];
    notes[selectionData.id] = selectionNoteRecord(existing, text);
    const didWrite = writeSelectionNotes(notes);
    dialog.status.textContent = didWrite ? (text.trim() ? labels.saved : labels.highlighted) : labels.failed;
    if (didWrite && refreshHighlights) refreshSelectionNoteHighlights(labels);
    return didWrite;
  };

  const flushPendingSelectionNoteSave = () => {
    if (!selectionNoteSaveTimer) return;
    window.clearTimeout(selectionNoteSaveTimer);
    selectionNoteSaveTimer = 0;
    saveCurrentSelectionNote();
  };

  const openDialogForSelection = data => {
    selectionData = data;
    const notes = readSelectionNotes();
    let existing = notes[selectionData.id];
    let markerWriteFailed = false;
    if (!existing && selectionData.text) {
      existing = selectionNoteRecord(null, "");
      if (writeSelectionNotes({ ...notes, [selectionData.id]: existing })) {
        refreshSelectionNoteHighlights(labels);
      } else {
        markerWriteFailed = true;
      }
    }
    const nl = String.fromCharCode(10);
    dialog.excerpt.textContent = selectionData.wasTruncated
      ? `${selectionData.text}${nl}${labels.truncated}`
      : selectionData.text;
    dialog.note.value = existing?.note || "";
    dialog.status.textContent = markerWriteFailed
      ? labels.failed
      : (existing ? (existing.note ? labels.saved : labels.highlighted) : labels.empty);
    announceSelectionDialogOpen(dialog.panel);
    dialog.panel.hidden = false;
    dialog.note.focus();
  };

  const openDialogForStoredNote = note => {
    flushPendingSelectionNoteSave();
    selectionData = {
      id: note.id,
      pageKey: note.pageKey || selectionNotesPageKey(),
      title: note.title || currentPageHeading(labels),
      url: note.url || location.href.split("#")[0],
      text: note.quote || "",
      wasTruncated: false,
      quoteIndex: Number.isFinite(note.quoteIndex) ? note.quoteIndex : -1,
    };
    hideButton();
    openDialogForSelection(selectionData);
  };

  const closeDialog = () => {
    flushPendingSelectionNoteSave();
    dialog.panel.hidden = true;
    dialog.status.textContent = "";
    scheduleSelectionRefresh();
  };

  document.addEventListener(SELECTION_DIALOG_OPEN_EVENT, event => {
    if (event.detail?.panel === dialog.panel) return;
    if (!dialog.panel.hidden) closeDialog();
  });

  const exportAllSelectionNotes = () => {
    const notes = readSelectionNotes();
    if (!selectionNoteEntries(notes).length) {
      dialog.status.textContent = labels.none;
      return;
    }
    const blob = new Blob([selectionNotesToMarkdown(notes, labels)], { type: "text/markdown;charset=utf-8" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `afml-selection-notes-${new Date().toISOString().slice(0, 10)}.md`;
    document.body.appendChild(link);
    link.click();
    URL.revokeObjectURL(link.href);
    link.remove();
  };

  button.addEventListener("mousedown", event => {
    event.preventDefault();
  });
  button.addEventListener("click", () => {
    const nextSelectionData = selectionDataForNote(labels) || pendingSelectionData || selectionData;
    if (!nextSelectionData) return;
    if (!dialog.panel.hidden && nextSelectionData.id !== selectionData?.id) {
      flushPendingSelectionNoteSave();
    }
    pendingSelectionData = null;
    hideButton();
    openDialogForSelection(nextSelectionData);
  });
  dialog.close.addEventListener("click", closeDialog);
  dialog.save.addEventListener("click", saveCurrentSelectionNote);
  dialog.copyQuote.addEventListener("click", async () => {
    if (!selectionData?.text) return;
    await writeClipboardText(selectionData.text);
    dialog.status.textContent = labels.copied;
  });
  dialog.exportNotes.addEventListener("click", exportAllSelectionNotes);
  dialog.remove.addEventListener("click", () => {
    if (!selectionData || !window.confirm(labels.deleteConfirm)) return;
    const notes = readSelectionNotes();
    delete notes[selectionData.id];
    writeSelectionNotes(notes);
    dialog.note.value = "";
    dialog.status.textContent = labels.deleted;
    refreshSelectionNoteHighlights(labels);
  });
  dialog.note.addEventListener("input", () => {
    window.clearTimeout(selectionNoteSaveTimer);
    dialog.status.textContent = dialog.note.value.trim() ? labels.saving : labels.highlighted;
    selectionNoteSaveTimer = window.setTimeout(saveCurrentSelectionNote, SELECTION_NOTE_SAVE_DELAY_MS);
  });
  dialog.note.addEventListener("keydown", event => {
    if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      saveCurrentSelectionNote();
    }
  });
  document.addEventListener("selectionchange", scheduleSelectionRefresh);
  document.addEventListener("mouseup", scheduleSelectionRefresh);
  document.addEventListener("touchend", scheduleSelectionRefresh);
  document.addEventListener("keyup", event => {
    if (event.key === "Escape") {
      if (!dialog.panel.hidden) closeDialog();
      hideButton();
      return;
    }
    scheduleSelectionRefresh();
  });
  window.addEventListener("scroll", () => {
    if (!button.hidden) refreshSelectionButton();
  }, { passive: true });
  window.addEventListener("resize", scheduleSelectionRefresh);
  article.addEventListener("click", event => {
    const highlight = event.target.closest(".selection-note-highlight");
    if (!highlight || !article.contains(highlight)) return;
    const note = readSelectionNotes()[highlight.dataset.selectionNoteId];
    if (!note) {
      refreshSelectionNoteHighlights(labels);
      return;
    }
    event.preventDefault();
    event.stopPropagation();
    openDialogForStoredNote(note);
  });
  article.addEventListener("keydown", event => {
    if (event.key !== "Enter" && event.key !== " ") return;
    const highlight = event.target.closest(".selection-note-highlight");
    if (!highlight || !article.contains(highlight)) return;
    const note = readSelectionNotes()[highlight.dataset.selectionNoteId];
    if (!note) return;
    event.preventDefault();
    openDialogForStoredNote(note);
  });
  window.addEventListener("storage", event => {
    if (event.key === SELECTION_NOTES_STORAGE_KEY) refreshSelectionNoteHighlights(labels);
  });
  window.addEventListener("beforeunload", () => {
    flushPendingSelectionNoteSave();
  });
  refreshSelectionNoteHighlights(labels);
};

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", installSelectionNotes);
} else {
  installSelectionNotes();
}

document.addEventListener("click", async event => {
  const button = event.target.closest(".copy-code");
  if (!button) return;
  const listing = button.closest(".code-listing");
  const code = listing && listing.querySelector("code");
  if (!code) return;
  const text = code.innerText;
  const previous = button.textContent;
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.setAttribute("readonly", "");
    textarea.style.position = "fixed";
    textarea.style.left = "-9999px";
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand("copy");
    textarea.remove();
  }
  button.textContent = "Copied";
  window.setTimeout(() => {
    button.textContent = previous || "Copy";
  }, 1200);
});

const tocSearch = document.querySelector(".toc-search");
const tocEntries = [...document.querySelectorAll("[data-toc-entry]")];
if (tocSearch && tocEntries.length) {
  const filterContents = () => {
    const query = tocSearch.value.trim().toLowerCase();
    for (const entry of tocEntries) {
      const matches = !query || entry.dataset.search.includes(query);
      entry.hidden = !matches;
      const details = entry.querySelector(".toc-details");
      if (details) details.open = Boolean(query && matches);
    }
    for (const part of document.querySelectorAll(".toc-part")) {
      part.hidden = !part.querySelector("[data-toc-entry]:not([hidden])");
    }
  };
  tocSearch.addEventListener("input", filterContents);
}
""",
        encoding="utf-8",
    )


def build() -> None:
    xml_root = build_xml()
    pages = extract_layout_pages()
    if BOOK.exists():
        shutil.rmtree(BOOK)
    BOOK.mkdir(parents=True)
    image_map = copy_xml_images(xml_root)
    ensure_chapter_04_media()
    ensure_chapter_05_media()
    ensure_chapter_10_media()
    ensure_chapter_11_media()
    ensure_chapter_13_media()
    ensure_chapter_15_media()
    ensure_chapter_16_media()
    ensure_chapter_17_media()
    ensure_chapter_18_media()
    ensure_chapter_19_media()
    ensure_chapter_20_media()
    ensure_chapter_21_media()
    ensure_chapter_22_media()
    write_css()
    write_js()

    for chapter in CHAPTERS:
        blocks, sections = parse_chapter(chapter, pages, image_map)
        blocks, sections = filter_exercise_blocks(blocks, sections)
        content = render_blocks(chapter, blocks)
        (BOOK / chapter.file).write_text(page_shell(chapter, content, sections), encoding="utf-8")

    write_book_index()
    write_root_index()
    if TMP.exists():
        shutil.rmtree(TMP)
    try:
        TMP.parent.rmdir()
    except OSError:
        pass


if __name__ == "__main__":
    build()
