import re
from typing import List

def chunk_text_for_gliner(text: str, max_chars: int = 750) -> List[str]:
    """
    Split text into bounded chunks below GLiNER's 384-token limit (~750 chars / ~150 words),
    preserving sentence and bullet boundaries without dropping text.
    """
    if not text or not text.strip():
        return []

    # Split into logical sentence/bullet segments
    raw_lines = text.splitlines()
    segments: List[str] = []
    for line in raw_lines:
        line = line.strip()
        if not line:
            continue
        # Split line on sentence boundaries while keeping punctuation
        sentences = re.split(r'(?<=[.!?])\s+', line)
        for s in sentences:
            s = s.strip()
            if s:
                segments.append(s)

    chunks: List[str] = []
    current_chunk = ""

    for seg in segments:
        # If adding this segment fits within budget
        if len(current_chunk) + (1 if current_chunk else 0) + len(seg) <= max_chars:
            current_chunk = (current_chunk + " " + seg).strip() if current_chunk else seg
        else:
            if current_chunk:
                chunks.append(current_chunk)
                current_chunk = ""
            
            # If a single segment is longer than max_chars, split on punctuation/words
            if len(seg) > max_chars:
                words = seg.split()
                sub_chunk = ""
                for w in words:
                    if len(sub_chunk) + (1 if sub_chunk else 0) + len(w) <= max_chars:
                        sub_chunk = (sub_chunk + " " + w).strip() if sub_chunk else w
                    else:
                        if sub_chunk:
                            chunks.append(sub_chunk)
                        sub_chunk = w
                current_chunk = sub_chunk
            else:
                current_chunk = seg

    if current_chunk:
        chunks.append(current_chunk)

    return chunks

# Test on a 3000 character document
long_doc = (
    "Requirement 1: Hands-on experience with LangChain and LlamaIndex for building LLM applications. " * 5 + "\n" +
    "Requirement 2: Proficient in Qdrant vector database and Redis caching mechanisms. " * 5 + "\n" +
    "Requirement 3: Advanced knowledge of Apache Kafka, Kubernetes cluster orchestration, and Prometheus. " * 5
)
chunks = chunk_text_for_gliner(long_doc, max_chars=750)
print(f"Total doc length: {len(long_doc)} chars")
print(f"Number of chunks: {len(chunks)}")
for i, c in enumerate(chunks):
    print(f"  Chunk {i}: len={len(c)} chars, words={len(c.split())}")
    assert len(c) <= 750, f"Chunk {i} exceeded max_chars: {len(c)}"
print("All chunks strictly within budget!")
