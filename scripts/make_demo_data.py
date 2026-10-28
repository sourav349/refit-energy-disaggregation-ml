"""Creates CLEARLY SYNTHETIC data to test functionality, NOT usable as REFIT evidence."""
import argparse
from pathlib import Path
import numpy as np
import pandas as pd


def generate(root:Path, days=21, seed=77):
    (root/'data/raw').mkdir(parents=True,exist_ok=True)
    (root/'data/cleaned').mkdir(parents=True,exist_ok=True)
    cols = {1:5,2:2,3:6,5:3}
    rng = np.random.default_rng(seed)
    # Use UTC timestamps; explicit synthetic time range.
    for house, wash_col in cols.items():
        t = pd.date_range('2014-09-01',periods=days*1440,freq='1min',tz='UTC')
        n=len(t)
        wash=np.zeros(n)
        for day in range(days):
            if rng.uniform()<.75:
                start = day*1440 + int(rng.integers(8*60,19*60))
                duration=int(rng.integers(42,100))
                end = min(start+duration,n)
                x=np.arange(end-start)
                # Highly simplified synthetic washer, labelled as such.
                wash[start:end] = np.maximum(0, rng.normal(90,25,len(x)))
                wash[start+3:min(start+15,end)] += 1650 + house*40
                wash[start+25:min(start+33,end)] += 900
        fridge = 90*(np.arange(n)%55 < 25).astype(float)
        other = rng.normal(150 + 12*house,30,n).clip(0)
        kettle = (rng.uniform(size=n)<.0025)*2000
        aggregate = (wash+fridge+other+kettle).clip(0)
        data = {'Time':t.strftime('%Y-%m-%d %H:%M:%S'),'Unix':t.asi8//10**9,'Aggregate':np.round(aggregate)}
        for i in range(1,10):data[f'Appliance{i}']=np.zeros(n)
        data[f'Appliance{wash_col}']=np.round(wash)
        data['Appliance1']=np.round(fridge) if wash_col != 1 else np.round(wash)
        if house==1: # keep raw appliance 1 as a refrigerator and appliance 5 as washer
            data['Appliance1']=np.round(fridge)
        data['Issues']=np.zeros(n,dtype=int)
        frame=pd.DataFrame(data)
        frame.to_csv(root/f'data/cleaned/CLEAN_House{house}.csv',index=False)
        if house==1:
            # emulate irregular 8-second data with timestamp duplications, small/long outages.
            repeated=np.repeat(np.arange(n),7)
            raw=frame.iloc[repeated].copy().reset_index(drop=True)
            offset=np.tile(np.array([0,8,16,24,32,40,48]),n)
            raw['Unix'] = raw['Unix'].to_numpy() + offset
            raw['Time']=pd.to_datetime(raw['Unix'],unit='s',utc=True).dt.strftime('%Y-%m-%d %H:%M:%S')
            raw=raw.drop(columns=['Issues'])
            raw=raw.drop(index=range(24*7,25*7)) # bounded 1-minute gap
            raw=raw.drop(index=range(3*24*60*7,3*24*60*7+60*7)) # 60-minute outage
            raw=pd.concat([raw,raw.iloc[250:251]],ignore_index=True)
            raw.to_csv(root/'data/raw/RAW_House1.csv',index=False)
    (root/'data/SYNTHETIC_DEMO_ONLY.txt').write_text('SIMULATED DATA: DO NOT DESCRIBE AS REFIT OR INCLUDE AS MEASURED RESULTS.\n',encoding='utf-8')
    print('Synthetic test CSVs generated under',root/'data')

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--root',type=Path,default=Path('.')); p.add_argument('--days',type=int,default=21)
    a=p.parse_args();generate(a.root,a.days)
