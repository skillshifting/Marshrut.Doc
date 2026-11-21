from pathlib import Path
from .seed import create_seed
from .ml import Classifier

base=Path(__file__).resolve().parents[1]/'data'
base.mkdir(exist_ok=True)
create_seed(base/'training.csv')
if __name__=='__main__':
    result=Classifier(base/'training.csv',base/'classifier.joblib',base/'model_meta.json',load_existing=False).train()
    print(f"Версия: {result['version']}; примеров: {result['count']}; тест: {result['test_count']}; доля верных на синтетической отложенной выборке: {result['accuracy']:.3f}")
