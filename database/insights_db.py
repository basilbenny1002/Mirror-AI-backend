# import chromadb

# client = chromadb.Client()
# collection = client.get_or_create_collection("insights")

# def save_insight(session_id: str, text: str):
#     collection.add(
#         documents=[text],
#         ids=[session_id + "_" + str(hash(text))]
#     )

# def search_insight(query: str, n=3):
#     results = collection.query(
#         query_texts=[query],
#         n_results=n
#     )
#     return results["documents"][0] if results["documents"] else []
