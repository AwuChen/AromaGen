import os
from os import path
from pathlib import Path
import matplotlib.pyplot as plt
from wordcloud import WordCloud


ROOT = Path(__file__).resolve().parent
COMPOSE_PATH = ROOT / "aromagen" / "data" / "dialogue" / "compose.txt"
textFile = COMPOSE_PATH.parent / "human_input.txt"

'''the path would have to go to the jsonl files
aromagen/agents/data/dialogue/ (the 6 dialogue files that ends with .jsonl)
from there, I pick out the first compose events for each session_id because it is a long list across each file, I might have to extract all the first compose for each session_ids in every single .jsonl files then transfer to a .txt file which I then use for the word cloud generation'''





with open(textFile, "r", encoding="utf-8") as f:
    text = f.read()


stopwords = set([
    "the", "and", "to", "of", "a", "in", "is", "it", "that", "for", "on",
    "with", "as", "this", "are", "be", "by", "or", "from", "at", "an",
    "not", "but", "if", "they", "you", "we", "can", "all", "so","really",
     "Yeah", "Okay", "actually", "Oh", "know", "think", "well", "something", 
     "kind", "one", "thing", "going", "see", "new", "first", "let", "maybe", "I",
     "like", "was", "my", "there", "just", "have", "me", "had", "what", "do", "around",
      "then", "about", "would", "I'm", "very", "when", "because", "your", "some", "also",
       "were", "could", "should", "don't", "you're", "make", "went", "he", "she", "part", 
       "use", "up", "give", "met", "more", "every", "want", "Thank", "hear","where", "nice",
       "lot", "right", "her nose", "Her crinkled", "beneath her", "describe"
])

wordcloud = WordCloud(
    width=800, 
    height=400, 
    stopwords=stopwords,
    background_color='white').generate(text)

plt.figure(figsize=(10, 5))
plt.imshow(wordcloud, interpolation='bilinear')
plt.axis('off')
plt.tight_layout(pad=0)
plt.savefig('wordcloud_filtered2.png', dpi=300, bbox_inches='tight')
plt.show()

