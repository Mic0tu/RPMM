import { DishCard } from "../../components/DishCard";
import { getMenuItems } from "../../lib/api";

export const revalidate = 60; 

export default async function MenuPage() {
  const items = await getMenuItems();

  return (
    <main className="mx-auto max-w-5xl px-6 py-10">
      <h1 className="text-3xl font-bold tracking-tight">Меню</h1>
      <p className="mt-2 text-neutral-600">
        Данные отрендерены на сервере (SSR).
      </p>
      
      <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {items.map((item) => (
          <DishCard key={item.id} item={item} />
        ))}
      </div>
    </main>
  );
}