"""Insert demo menu dishes without duplicating existing names."""
from app.database import SessionLocal
from app.models import MenuItem

SAMPLE_MENU = (
    ("Сырники со сметаной", 240.0),
    ("Куриный суп с лапшой", 190.0),
    ("Паста с томатами", 320.0),
    ("Салат с печёной свёклой", 210.0),
    ("Яблочный пирог", 160.0),
)


def main() -> None:
    db = SessionLocal()
    try:
        existing = {name for (name,) in db.query(MenuItem.name).all()}
        for name, price in SAMPLE_MENU:
            if name not in existing:
                db.add(MenuItem(name=name, price=price, is_available=True))
        db.commit()
        print("Demo menu is ready.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
