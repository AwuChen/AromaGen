import pandas as pd
import numpy as np

df = pd.read_csv("user_study_result.csv")
df['is_correct'] = df['is_correct'].astype(str).str.upper() == 'TRUE'
df['is_duplicate_submission'] = df['is_duplicate_submission'].astype(str).str.upper() == 'TRUE'
n_before = len(df)
df = df[~df['is_duplicate_submission']].copy()
if n_before != len(df):
    print(f"Dropped {n_before - len(df)} row(s) flagged is_duplicate_submission=TRUE")

df['response_timestamp'] = pd.to_datetime(df['response_timestamp'], dayfirst=True)
df['day'] = df['response_timestamp'].dt.date.astype(str)

# descriptor -> cluster taxonomy, built from the fixed ratio vector list
taxonomy = {
    "Floral": ["jasmine", "lilac", "rose", "lavender"],
    "Citrus": ["lemony", "currant", "tangy", "guava"],
    "Woody & Resinous": ["sandalwood", "Myrrh", "Cedar", "saffron", "piney"],
    "Herbal & Cooling": ["minty", "wintergreen", "rosemary", "eucalyptus"],
    "Spice": ["anise", "cinnamon", "peppery", "cumin", "nutmeg"],
    "Sweet & Gourmand": ["Honeyed", "Vanilla", "Maple-syrup", "Coconut"],
    "Roasted & Smoky": ["woodsmoke", "fresh_bread", "toasty", "Burnt", "smoky"],
    "Fermented & Sour": ["vinegar-like", "yeasty", "sour_milk", "butyric"],
    "Putrid & Decay": ["rotten-egg", "musty", "rotten_fish", "feces"],
    "Body & Animalic": ["fishy", "wet_dog", "bad_breath", "sweaty"],
    "Chemical & Solvent": ["burnt_rubber", "disinfectant", "chlorine", "nail-polisher"],
    "Perfumed & Clean": ["aftershave", "air_freshener", "perfumer", "skin-care"],
}

desc2cluster = {}
for cluster, descs in taxonomy.items():
    for d in descs:
        desc2cluster[d.lower()] = cluster

def lookup_cluster(desc):
    if pd.isna(desc):
        return None
    key = str(desc).strip().lower()
    c = desc2cluster.get(key)
    if c is None:
        print(f"WARNING: descriptor '{desc}' not found in taxonomy")
    return c

opt_cols = ['option_a', 'option_b', 'option_c', 'option_d']

# check every descriptor maps
all_descs = set(df['descriptor'].unique()) | set(pd.unique(df[opt_cols].values.ravel()))
unmapped = [d for d in all_descs if lookup_cluster(d) is None]
print("Unmapped descriptors:", unmapped)

def selected_descriptor(row):
    return row[opt_cols[int(row['selected_index'])]]

def correct_descriptor(row):
    return row[opt_cols[int(row['correct_index'])]]

df['selected_descriptor'] = df.apply(selected_descriptor, axis=1)
df['correct_descriptor'] = df.apply(correct_descriptor, axis=1)
df['selected_cluster'] = df['selected_descriptor'].apply(lookup_cluster)
df['target_cluster'] = df['cluster']  # given column, should equal cluster of correct_descriptor

# sanity check: does correct_descriptor's cluster match the given 'cluster' column?
df['correct_desc_cluster'] = df['correct_descriptor'].apply(lookup_cluster)
mismatch = df[df['correct_desc_cluster'] != df['target_cluster']]
if len(mismatch):
    print("\nRows where correct_descriptor's taxonomy cluster != given cluster column:")
    print(mismatch[['participant_id','trial_number','cluster','correct_descriptor','correct_desc_cluster']])

# exact accuracy (descriptor-level) already given as is_correct
# class/cluster-level accuracy: selected option's cluster matches target cluster
df['class_correct'] = df['selected_cluster'] == df['target_cluster']

print("\n=== Overall ===")
print(f"N trials: {len(df)}")
print(f"Exact descriptor accuracy: {df['is_correct'].mean():.1%}")
print(f"Class-level (cluster) accuracy: {df['class_correct'].mean():.1%}")

print("\n=== Accuracy per target cluster ===")
cluster_stats = df.groupby('target_cluster').agg(
    n=('trial_number', 'count'),
    exact_acc=('is_correct', 'mean'),
    class_acc=('class_correct', 'mean'),
).sort_values('class_acc', ascending=False)
print(cluster_stats.to_string(float_format=lambda x: f"{x:.1%}" if x <= 1 else str(x)))

print("\n=== Accuracy per participant ===")
participant_stats = df.groupby('participant_id').agg(
    n=('trial_number', 'count'),
    exact_acc=('is_correct', 'mean'),
    class_acc=('class_correct', 'mean'),
)
print(participant_stats.to_string())

print("\n=== Accuracy per day ===")
day_stats = df.groupby('day').agg(
    n_participants=('participant_id', 'nunique'),
    n=('trial_number', 'count'),
    exact_acc=('is_correct', 'mean'),
    class_acc=('class_correct', 'mean'),
)
print(day_stats.to_string())

print("\n=== Accuracy per smell (correct_descriptor) ===")
smell_stats = df.groupby('correct_descriptor').agg(
    n=('trial_number', 'count'),
    exact_acc=('is_correct', 'mean'),
    class_acc=('class_correct', 'mean'),
).sort_values('class_acc', ascending=False)
print(smell_stats.to_string())

print("\n=== Confidence vs correctness ===")
print("Mean confidence when exact-correct:", df.loc[df['is_correct'], 'confidence_1to5'].mean())
print("Mean confidence when exact-wrong:  ", df.loc[~df['is_correct'], 'confidence_1to5'].mean())
print("Mean confidence when class-correct:", df.loc[df['class_correct'], 'confidence_1to5'].mean())
print("Mean confidence when class-wrong:  ", df.loc[~df['class_correct'], 'confidence_1to5'].mean())

print("\n=== Familiarity vs correctness ===")
print("Mean familiarity when exact-correct:", df.loc[df['is_correct'], 'familiarity_1to5_for_descriptor'].mean())
print("Mean familiarity when exact-wrong:  ", df.loc[~df['is_correct'], 'familiarity_1to5_for_descriptor'].mean())
print("Mean familiarity when class-correct:", df.loc[df['class_correct'], 'familiarity_1to5_for_descriptor'].mean())
print("Mean familiarity when class-wrong:  ", df.loc[~df['class_correct'], 'familiarity_1to5_for_descriptor'].mean())

# correlation
print("\n=== Correlations (point-biserial via .corr) ===")
print("confidence vs is_correct:", df['confidence_1to5'].corr(df['is_correct'].astype(int)))
print("confidence vs class_correct:", df['confidence_1to5'].corr(df['class_correct'].astype(int)))
print("familiarity vs is_correct:", df['familiarity_1to5_for_descriptor'].corr(df['is_correct'].astype(int)))
print("familiarity vs class_correct:", df['familiarity_1to5_for_descriptor'].corr(df['class_correct'].astype(int)))

df.to_csv("enriched.csv", index=False)
