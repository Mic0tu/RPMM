import Link from "next/link";
import { notFound } from "next/navigation";
import { formatPrice, getMenuItem } from "../../../lib/api";

type PageProps = {
  params: Promise<{ id: string }>;
};

export async function generateMetadata({ params }: PageProps) {
  const { id } = await params;
  const item = await getMenuItem(id);
  
  if (!item) return { title: "Блюдо не найдено" };
  
  return {
    title: `${item.name} - Сириус.Еда`,
    description: `Закажите ${item.name} за ${item.price} руб.`,
  };
}

export default async function MenuItemPage({ params }: PageProps) {
  const { id } = await params;
  const item = await getMenuItem(id);

  if (!item) notFound(); 

  return (
    <main className="mx-auto max-w-3xl px-6 py-12">
      <Link href="/menu" className="text-sm font-medium text-orange-600 hover:underline">
        ← Назад к меню
      </Link>
      <article className="mt-6 rounded-3xl border bg-white p-8 shadow-sm">
        <h1 className="text-3xl font-bold">{item.name}</h1>
        <p className="mt-4 text-2xl font-bold text-orange-600">
          {formatPrice(item.price)}
        </p>
      </article>
    </main>
  );
}