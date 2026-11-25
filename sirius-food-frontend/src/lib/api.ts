export const API_URL =
  process.env.API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export const PUBLIC_API_URL = process.env.NEXT_PUBLIC_API_URL ?? API_URL;

export type MenuItem = {
  id: number;
  name: string;
  price: number;
  is_available?: boolean;
  category?: string | null;
};

export async function getMenuItems(): Promise<MenuItem[]> {
  const response = await fetch(`${API_URL}/menu/items`, {
    next: { revalidate: 60 }, 
  });
  if (!response.ok) {
    throw new Error(`REST API вернул HTTP ${response.status}`);
  }
  return response.json();
}

export async function getMenuItem(id: number | string): Promise<MenuItem | null> {
  const numericId = Number(id);
  if (!Number.isInteger(numericId) || numericId <= 0) return null;

  const response = await fetch(`${API_URL}/menu/items/${numericId}`, {
    next: { revalidate: 60 },
  });
  if (response.status === 404) return null;
  if (!response.ok) {
    throw new Error(`REST API вернул HTTP ${response.status}`);
  }
  return response.json();
}

export function formatPrice(price: number): string {
  return new Intl.NumberFormat("ru-RU", {
    style: "currency",
    currency: "RUB",
    maximumFractionDigits: 0,
  }).format(price);
}