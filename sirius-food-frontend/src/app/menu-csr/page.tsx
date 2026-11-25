'use client'; // Это делает компонент клиентским (CSR)

import { useEffect, useState } from "react";
import { DishCard } from "../../components/DishCard";
import { getMenuItems } from "../../lib/api";

export default function MenuCSRPage() {
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Данные загружаются в браузере после того, как страница отрисуется
    getMenuItems().then((data) => {
      setItems(data);
      setLoading(false);
    });
  }, []);

  if (loading) return <div className="p-10 text-center">Загрузка (CSR)...</div>;

  return (
    <main className="mx-auto max-w-5xl px-6 py-10">
      <h1 className="text-3xl font-bold">Меню (CSR версия)</h1>
      <p className="text-red-600 mt-2">Эти данные загрузились в браузере (в Ctrl+U их не будет!)</p>
      <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {items.map((item) => (
          <DishCard key={item.id} item={item} />
        ))}
      </div>
    </main>
  );
}