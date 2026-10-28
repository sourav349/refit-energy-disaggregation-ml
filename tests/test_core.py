import numpy as np
import pandas as pd
from refit_nilm.core import assess_and_resample,detect_cycles,create_features,metrics,load_csv


def test_duplicates_last_wins_and_long_outage_is_nan():
    ts=pd.to_datetime(['2024-01-01T00:00:00Z','2024-01-01T00:00:00Z',
                        '2024-01-01T00:01:00Z','2024-01-01T00:05:00Z'])
    df=pd.DataFrame({'timestamp':ts,'Aggregate':[10,20,30,50],'Appliance5':[0,10,12,100]})
    m,q=assess_and_resample(df,['Appliance5'],raw=True,max_short_gap=2)
    assert q['duplicate_timestamps']==1
    assert m.iloc[0].Aggregate==20
    assert pd.isna(m.loc['2024-01-01T00:02:00Z','Aggregate']) # NaN in 3-min gap
    assert pd.isna(m.loc['2024-01-01T00:04:00Z','Aggregate'])


def test_short_gap_filled():
    ts=pd.to_datetime(['2024-01-01T00:00:00Z','2024-01-01T00:03:00Z'])
    df=pd.DataFrame({'timestamp':ts,'Aggregate':[100,150],'Appliance5':[10,40]})
    m,_=assess_and_resample(df,['Appliance5'],raw=True)
    assert m.loc['2024-01-01T00:01:00Z','Aggregate']==100
    assert m.loc['2024-01-01T00:02:00Z','Aggregate']==100


def test_cycle_does_not_cross_missing():
    idx=pd.date_range('2024-01-01',periods=80,freq='1min',tz='UTC')
    y=pd.Series(100.0,index=idx)
    y.iloc[20:40]=np.nan
    ev=detect_cycles(y,threshold_w=20,bridge_off_minutes=25)
    assert len(ev)==2
    assert ev.duration_min.tolist()==[20,40]


def test_features_are_causal_and_drop_nan_windows():
    idx=pd.date_range('2024-01-01',periods=45,freq='1min',tz='UTC')
    df=pd.DataFrame({'Aggregate':np.arange(45,dtype=float),'Appliance5':np.zeros(45)},index=idx)
    x=create_features(df,'Appliance5')
    assert x.iloc[0]['lag15']==0 and x.iloc[0]['aggregate_w']==15
    df.loc[idx[25],'Aggregate']=np.nan
    x2=create_features(df,'Appliance5')
    assert idx[27] not in x2.index


def test_metrics_zero_baseline():
    vals=metrics(np.array([0,0,100]),np.zeros(3))
    assert vals['mae_w']>0
    assert vals['recall_active']==0


def test_csv_headers_and_unix(tmp_path):
    fp=tmp_path/'CLEAN_House1.csv'
    pd.DataFrame({'Time':['2014-01-01 00:00:00'],'Unix':[1388534400],
                  'Aggregate':[110],'Appliance5':[100],'Issues':[0]}).to_csv(fp,index=False)
    df=load_csv(fp,['Appliance5'])
    assert df['Aggregate'].iloc[0]==110
    assert df['timestamp'].iloc[0].year==2014
