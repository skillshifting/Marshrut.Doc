import json
import re
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.pipeline import make_pipeline

from .seed import LABELS

def _norm(text):
    return ' '.join(re.findall(r'[а-яёa-z0-9]+', str(text).lower()))

def _groups(frame):
    """Join supplied scenario IDs and near duplicates into connected components."""
    texts = frame.text.map(_norm).tolist()
    vectorizer = TfidfVectorizer(analyzer='char', ngram_range=(3, 5))
    similarity = cosine_similarity(vectorizer.fit_transform(texts))
    parents = list(range(len(texts)))
    def root(i):
        while parents[i] != i:
            parents[i] = parents[parents[i]]
            i = parents[i]
        return i
    def merge(a, b):
        parents[root(a)] = root(b)
    by_id = {}
    for i, row in frame.iterrows():
        group = str(row.get('scenario_group', '')).strip()
        if group and group.lower() != 'nan':
            if group in by_id: merge(i, by_id[group])
            by_id[group] = i
    for i in range(len(texts)):
        for j in range(i):
            if similarity[i,j] >= .78 or texts[i] == texts[j]: merge(i,j)
    return [root(i) for i in range(len(texts))]

class Classifier:
    def __init__(self, data: Path, model: Path, meta: Path, load_existing: bool = True):
        self.data, self.model_path, self.meta_path = data, model, meta
        self.pipeline = None
        self.meta = {}
        self.reference = None
        if load_existing and model.exists() and meta.exists():
            saved = json.loads(meta.read_text(encoding='utf-8'))
            # scikit-learn does not promise portable pickle files across versions.
            if saved.get('sklearn_version') == sklearn.__version__: self.load()

    def load(self):
        bundle = joblib.load(self.model_path)
        self.pipeline, self.reference = bundle['pipeline'], bundle['reference']
        self.meta = json.loads(self.meta_path.read_text(encoding='utf-8'))

    def train(self):
        frame = pd.read_csv(self.data, encoding='utf-8-sig').fillna('')
        if not {'text','label'}.issubset(frame): raise ValueError('В CSV нужны столбцы text и label')
        frame = frame[frame.text.astype(str).str.strip().str.len() >= 8].reset_index(drop=True)
        if set(frame.label) != set(LABELS): raise ValueError('Для обучения нужны примеры каждой из пяти категорий')
        groups = np.array(_groups(frame))
        group_labels = {}
        for group, label in zip(groups, frame.label):
            if group in group_labels and group_labels[group] != label:
                raise ValueError('Одинаковые или перефразированные сообщения имеют разные категории')
            group_labels[group] = label
        counts = {label: len({groups[i] for i in frame.index if frame.label[i] == label}) for label in LABELS}
        if min(counts.values()) < 3: raise ValueError('Нужно не менее трёх независимых сценариев каждой категории')
        # Split groups separately per class: every category is present in holdout.
        rng = np.random.default_rng(42)
        test_groups = set()
        for label in LABELS:
            owned = np.array([g for g, value in group_labels.items() if value == label])
            rng.shuffle(owned)
            test_groups.update(owned[:max(1, round(len(owned) * .25))].tolist())
        test = np.array([g in test_groups for g in groups]); train = ~test
        build = lambda: make_pipeline(TfidfVectorizer(ngram_range=(1,2), sublinear_tf=True, min_df=1), LogisticRegression(max_iter=1600, class_weight='balanced'))
        check = build().fit(frame.text[train], frame.label[train])
        prediction = check.predict(frame.text[test])
        matrix = confusion_matrix(frame.label[test], prediction, labels=LABELS).tolist()
        report = classification_report(frame.label[test], prediction, labels=LABELS, output_dict=True, zero_division=0)
        self.pipeline = build().fit(frame.text, frame.label)
        self.reference = self.pipeline.named_steps['tfidfvectorizer'].transform(frame.text)
        version = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        self.meta = dict(version=version, sklearn_version=sklearn.__version__, count=len(frame), train_count=int(train.sum()), test_count=int(test.sum()),
                         groups=len(set(groups)), test_groups=len(test_groups), accuracy=float(accuracy_score(frame.label[test], prediction)),
                         macro_f1=float(report['macro avg']['f1-score']), matrix=matrix, labels=LABELS,
                         caution='Синтетические данные. Отложенная проверка разделяет сценарии и близкие перефразирования; качество на реальных происшествиях не доказано. Небольшая проверочная выборка не даёт надёжной оценки эксплуатации.')
        joblib.dump(dict(pipeline=self.pipeline, reference=self.reference), self.model_path)
        self.meta_path.write_text(json.dumps(self.meta, ensure_ascii=False, indent=2), encoding='utf-8')
        return self.meta

    def predict(self, text):
        if self.pipeline is None: raise ValueError('Модель не обучена')
        probabilities = self.pipeline.predict_proba([text])[0]
        scores = dict(zip(self.pipeline.classes_, map(float, probabilities)))
        vec = self.pipeline.named_steps['tfidfvectorizer'].transform([text])
        similarity = float(cosine_similarity(vec, self.reference).max()) if vec.nnz else 0.
        confidence = max(scores.values())
        low = similarity < .20 or confidence < .42
        return dict(label=max(scores, key=scores.get), scores=scores, low_confidence=low,
                    closest_training_similarity=similarity,
                    confidence_note='Текст далёк от учебных примеров или оценки классов близки; нужна проверка специалиста.' if low else 'Оценки классов не являются подтверждённой точностью на реальных сообщениях.')
