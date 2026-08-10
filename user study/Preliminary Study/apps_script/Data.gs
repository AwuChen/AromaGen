/**
 * Study vocabulary: the 50 descriptors across 12 clusters, and the
 * distractor table (target -> 3 distractors). Ported 1:1 from
 * study_design.py -- keep the two files in sync if the descriptor list or
 * distractor logic changes.
 *
 * Distractor rule note (see study protocol, "Construct the four response
 * options"): rule 1 says to prefer Sniffin' Sticks / UPSIT distractors when
 * the target descriptor appears in those tests. This table implements only
 * rule 2 (cluster-proximity picks) for all 50 words -- nobody has
 * cross-checked which of these 50 overlap the real Sniffin'/UPSIT item
 * banks yet, so treat this as the fallback set pending that check.
 *
 * Distractor structure (per user spec): target + 2 "near" distractors +
 * 1 "far" distractor.
 *   - The 12 clusters split into two families of 6: PLEASANT_CLUSTERS
 *     (Floral, Citrus, Woody & Resinous, Herbal & Cooling, Spice,
 *     Sweet & Gourmand) and the other 6 (Roasted & Smoky, Fermented &
 *     Sour, Putrid & Decay, Body & Animalic, Chemical & Solvent,
 *     Perfumed & Clean).
 *   - NEAR_CLUSTERS[cluster] gives that cluster's 2 fixed near-neighbors,
 *     always from the SAME family (a "next two in a fixed ring" pattern
 *     the user specified explicitly per cluster) -- one distractor drawn
 *     from each.
 *   - The far distractor is drawn from the OTHER family's 6 clusters,
 *     round-robin across all descriptors sharing that far pool (so usage
 *     balances evenly across all 6 far clusters, not just one or two),
 *     with a further rotation for which specific word within the chosen
 *     far cluster. See the parent folder's Python prototype for the
 *     generation code and balance verification.
 */

var CLUSTERS = {
  "Floral": ["jasmine", "lilac", "rose", "lavender"],
  "Citrus": ["lemony", "currant", "tangy", "guava"],
  "Woody & Resinous": ["sandalwood", "Myrrh", "Cedar", "saffron", "piney"],
  "Herbal & Cooling": ["minty", "wintergreen", "rosemary", "eucalyptus"],
  "Spice": ["anise", "cinnamon", "peppery", "cumin", "nutmeg"],
  "Sweet & Gourmand": ["Honeyed", "Vanilla", "Maple-syrup", "Coconut"],
  "Roasted & Smoky": ["woodsmoke", "fresh_bread", "toasty", "smoky"],
  "Fermented & Sour": ["vinegar-like", "yeasty", "sour_milk", "butyric"],
  "Putrid & Decay": ["rotten-egg", "musty", "rotten_fish", "feces"],
  "Body & Animalic": ["fishy", "wet_dog", "bad_breath", "sweaty"],
  "Chemical & Solvent": ["burnt_rubber", "disinfectant", "chlorine", "nail-polisher"],
  "Perfumed & Clean": ["aftershave", "air_freshener", "perfumer", "skin-care"]
};

var DISTRACTOR_TABLE = {
  "jasmine": ["lemony", "sandalwood", "woodsmoke"],
  "lilac": ["currant", "Myrrh", "vinegar-like"],
  "rose": ["tangy", "Cedar", "rotten-egg"],
  "lavender": ["guava", "saffron", "fishy"],
  "lemony": ["sandalwood", "minty", "burnt_rubber"],
  "currant": ["Myrrh", "wintergreen", "aftershave"],
  "tangy": ["Cedar", "rosemary", "fresh_bread"],
  "guava": ["saffron", "eucalyptus", "yeasty"],
  "sandalwood": ["minty", "anise", "musty"],
  "Myrrh": ["wintergreen", "cinnamon", "wet_dog"],
  "Cedar": ["rosemary", "peppery", "disinfectant"],
  "saffron": ["eucalyptus", "cumin", "air_freshener"],
  "piney": ["minty", "nutmeg", "toasty"],
  "minty": ["Honeyed", "anise", "sour_milk"],
  "wintergreen": ["Vanilla", "cinnamon", "rotten_fish"],
  "rosemary": ["Maple-syrup", "peppery", "bad_breath"],
  "eucalyptus": ["Coconut", "cumin", "chlorine"],
  "anise": ["Honeyed", "jasmine", "perfumer"],
  "cinnamon": ["Vanilla", "lilac", "smoky"],
  "peppery": ["Maple-syrup", "rose", "butyric"],
  "cumin": ["Coconut", "lavender", "feces"],
  "nutmeg": ["Honeyed", "jasmine", "sweaty"],
  "Honeyed": ["jasmine", "lemony", "nail-polisher"],
  "Vanilla": ["lilac", "currant", "skin-care"],
  "Maple-syrup": ["rose", "tangy", "woodsmoke"],
  "Coconut": ["lavender", "guava", "vinegar-like"],
  "woodsmoke": ["vinegar-like", "rotten-egg", "jasmine"],
  "fresh_bread": ["yeasty", "musty", "lemony"],
  "toasty": ["sour_milk", "rotten_fish", "sandalwood"],
  "smoky": ["butyric", "feces", "minty"],
  "vinegar-like": ["rotten-egg", "fishy", "anise"],
  "yeasty": ["musty", "wet_dog", "Honeyed"],
  "sour_milk": ["rotten_fish", "bad_breath", "lilac"],
  "butyric": ["feces", "sweaty", "currant"],
  "rotten-egg": ["fishy", "burnt_rubber", "Myrrh"],
  "musty": ["wet_dog", "disinfectant", "wintergreen"],
  "rotten_fish": ["bad_breath", "chlorine", "cinnamon"],
  "feces": ["sweaty", "nail-polisher", "Vanilla"],
  "fishy": ["burnt_rubber", "aftershave", "rose"],
  "wet_dog": ["disinfectant", "air_freshener", "tangy"],
  "bad_breath": ["chlorine", "perfumer", "Cedar"],
  "sweaty": ["nail-polisher", "skin-care", "rosemary"],
  "burnt_rubber": ["aftershave", "woodsmoke", "peppery"],
  "disinfectant": ["air_freshener", "fresh_bread", "Maple-syrup"],
  "chlorine": ["perfumer", "toasty", "lavender"],
  "nail-polisher": ["skin-care", "smoky", "guava"],
  "aftershave": ["woodsmoke", "vinegar-like", "saffron"],
  "air_freshener": ["fresh_bread", "yeasty", "eucalyptus"],
  "perfumer": ["toasty", "sour_milk", "cumin"],
  "skin-care": ["smoky", "butyric", "Coconut"]
};

// Confirmed by user: exactly these 6 clusters play first (order among them
// randomized per participant), the remaining 6 play second (order among
// them also randomized). Not a smooth gradient -- a hard first-half/
// second-half split. Used ONLY for trial presentation order.
//
// NOTE: this is a DIFFERENT grouping from the "family" split the
// distractor table's far-pick balancing was generated against above --
// that one has Spice in the same family as Floral/Citrus/Woody/Herbal/
// Sweet, and Roasted & Smoky grouped with Fermented/Putrid/Body/Chemical/
// Perfumed instead. The two groupings serve different purposes (trial
// pacing vs. distractor semantic distance) and were specified
// independently; don't assume they match.
var PLEASANT_CLUSTERS = ["Floral", "Citrus", "Woody & Resinous",
  "Sweet & Gourmand", "Roasted & Smoky", "Herbal & Cooling"];

function descriptorToCluster_() {
  var map = {};
  for (var cluster in CLUSTERS) {
    CLUSTERS[cluster].forEach(function (d) { map[d] = cluster; });
  }
  return map;
}
