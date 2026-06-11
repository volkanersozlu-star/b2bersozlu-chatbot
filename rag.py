import os
from typing import Optional

from dotenv import load_dotenv
import chromadb
from sentence_transformers import SentenceTransformer
from openai import OpenAI

load_dotenv()

CHROMA_DIR = "chroma_db"
EMBED_MODEL = "all-MiniLM-L6-v2"

_embedder = None
_client   = None


def _get_embedder():
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer(EMBED_MODEL)
    return _embedder


def _get_collection(tenant_id: str):
    name = f"tenant_{tenant_id.replace('-', '_')}"
    db   = chromadb.PersistentClient(path=CHROMA_DIR)
    return db.get_or_create_collection(name)


def _get_llm_client():
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=os.environ["DEEPSEEK_API_KEY"],
            base_url="https://api.deepseek.com/v1",
        )
    return _client


def retrieve(query: str, k: int = 4, tenant_id: str = "default") -> list:
    embedding = _get_embedder().encode([query]).tolist()[0]
    results   = _get_collection(tenant_id).query(
        query_embeddings=[embedding],
        n_results=k,
        include=["documents"],
    )
    return results["documents"][0] if results["documents"] else []


def generate(query: str, chunks: list, history: Optional[list] = None) -> str:
    if not chunks:
        return "Bu konuda yüklenen belgelerde bilgi bulunamadı."

    context = "\n\n---\n\n".join(chunks)
    system_prompt = (
        "Sen bir şirket destek asistanısın. Görevin yalnızca sana verilen şirket belgelerine "
        "dayanarak kullanıcıların sorularını Türkçe olarak yanıtlamaktır.\n\n"
        "Şu kurallara kesinlikle uy:\n"
        "1. Soru belgelerdeki konularla ilgiliyse belgelerden yararlanarak yanıtla.\n"
        "2. Soru konuyla ilgili ama belgede bilgi yoksa: "
        "'Bu konuda size yardımcı olacak bilgiye sahip değilim. "
        "Başka bir konuda yardımcı olabilir miyim?' de.\n"
        "3. Soru şirketle tamamen alakasızsa (hava durumu, politika, genel sohbet, "
        "kişisel sorular vb.): 'Bu konuyu maalesef konuşamıyorum. "
        "İsterseniz firmamızla ilgili sorularınızda size yardımcı olabilirim.' de.\n"
        "4. Asla belgelerde olmayan bilgiyi uydurup söyleme.\n"
        "5. Sohbet geçmişini dikkate alarak tutarlı yanıtlar ver.\n"
        "6. Yardımcı olamadığın durumlarda veya kullanıcı memnuniyetsizlik gösterdiğinde "
        "yanıtının sonuna şunu ekle: '📝 Öneri, görüş veya şikayetlerinizi iletmek için "
        "aşağıdaki Geri Bildirim butonunu kullanabilirsiniz.'\n\n"
        f"Şirket belgeleri:\n{context}"
    )

    recent_history = (history or [])[-10:]
    messages = [
        {"role": "system", "content": system_prompt},
        *recent_history,
        {"role": "user", "content": query},
    ]

    response = _get_llm_client().chat.completions.create(
        model="deepseek-chat",
        messages=messages,
        temperature=0.2,
    )
    return response.choices[0].message.content


def answer(query: str, history: Optional[list] = None, tenant_id: str = "default") -> str:
    chunks = retrieve(query, tenant_id=tenant_id)
    return generate(query, chunks, history)


def classify_feedback(text: str) -> str:
    """Classifies customer feedback as şikayet, öneri, or görüş."""
    try:
        response = _get_llm_client().chat.completions.create(
            model="deepseek-chat",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Kullanıcının yazdığı metni analiz et ve yalnızca şu üç kategoriden birini döndür:\n"
                        "- şikayet (olumsuz deneyim, sorun, memnuniyetsizlik)\n"
                        "- öneri (iyileştirme teklifi, yeni özellik isteği)\n"
                        "- görüş (genel yorum, nötr geri bildirim)\n"
                        "Sadece bu kelimelerden birini yaz, başka hiçbir şey ekleme."
                    ),
                },
                {"role": "user", "content": text},
            ],
            temperature=0,
            max_tokens=10,
        )
        result = response.choices[0].message.content.strip().lower()
        if result not in ("şikayet", "öneri", "görüş"):
            return "görüş"
        return result
    except Exception:
        return "görüş"
