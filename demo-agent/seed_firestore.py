import google.auth
from google.cloud import firestore

# HARDCODED project ID as required for Agent Platform compatibility
FIRESTORE_PROJECT = "qwiklabs-gcp-01-ffa5389289dd"


def get_firestore_client():
    creds, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/datastore"]
    )
    return firestore.Client(project=FIRESTORE_PROJECT, credentials=creds)


def seed_data():
    """Seeds default pantry items into Firestore."""
    db = get_firestore_client()
    items = [
        {
            "id": "pasta-spaghetti",
            "name": "Spaghetti",
            "category": "Grains",
            "quantity": 500,
            "unit": "grams",
            "expiration_date": "2026-12-01",
        },
        {
            "id": "tomato-sauce",
            "name": "Marinara Tomato Sauce",
            "category": "Canned Goods",
            "quantity": 2,
            "unit": "jars",
            "expiration_date": "2027-01-15",
        },
        {
            "id": "olive-oil",
            "name": "Extra Virgin Olive Oil",
            "category": "Oils & Condiments",
            "quantity": 1,
            "unit": "bottle",
            "expiration_date": "2027-06-30",
        },
        {
            "id": "garlic",
            "name": "Garlic Bulbs",
            "category": "Produce",
            "quantity": 4,
            "unit": "heads",
            "expiration_date": "2026-10-15",
        },
        {
            "id": "parmesan",
            "name": "Parmesan Cheese",
            "category": "Dairy",
            "quantity": 200,
            "unit": "grams",
            "expiration_date": "2026-11-20",
        },
    ]

    collection_ref = db.collection("pantry_items")
    for item in items:
        doc_id = item["id"]
        collection_ref.document(doc_id).set(item)
        print(f"Seeded pantry item: {item['name']} ({doc_id})")


if __name__ == "__main__":
    seed_data()
