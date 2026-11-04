# -*- coding: utf-8 -*-
"""Продуктовый анализ книжного магазина — версия для pandas.

Читает CSV из analysis/out/ (предварительно сгенерированные report.py).
Работает в окружении с pandas (например, conda env 'analytics').

Запуск (в VS Code):
    conda run -n analytics python analysis\\analyze.py
Либо выберите интерпретатор с pandas и запустите:
    python analysis\\analyze.py

Считает: GMV, AOV, ARPU/ARPPU, LTV, повторные покупки, когорты, гео, приток,
отмены. Пишет CSV в analysis/out/ + строит PNG-графики (matplotlib).
"""

import os
import csv
from datetime import datetime

import pandas as pd

HERE = os.path.dirname(__file__)
OUT = os.path.join(HERE, "out")


def load_orders():
    """Загружает заказы из orders.csv (с гео и статусом)."""
    path = os.path.join(OUT, "orders.csv")
    df = pd.read_csv(path, encoding="utf-8-sig")
    df["created_at"] = pd.to_datetime(df["created_at"])
    df["month"] = df["created_at"].dt.to_period("M").astype(str)
    return df


def fmt_money(x):
    return f"{x:,.2f} ₽"


def main():
    orders = load_orders()
    valid = orders[orders["status"] != "cancelled"].copy()
    cancelled = orders[orders["status"] == "cancelled"]

    print("=" * 78)
    print("СВОДНЫЕ МЕТРИКИ (e-commerce)")
    print("=" * 78)

    gmv = float(valid["amount"].sum())
    print(f"GMV (заказы кроме отменённых):      {fmt_money(gmv)}")
    print(f"  Всего заказов (не отменённых):     {len(valid)}")
    print(f"  Отменённых:                        {len(cancelled)}")

    aov = gmv / len(valid) if len(valid) else 0
    print(f"AOV (средний чек):                  {fmt_money(aov)}")

    # Медиана и разброс стоимости заказа (устойчивее к выбросам, чем среднее)
    aov_median = valid["amount"].median() if len(valid) else 0
    aov_std = valid["amount"].std() if len(valid) else 0
    print(f"AOV медиана:                        {fmt_money(aov_median)}")
    print(f"AOV std (разброс):                  {fmt_money(aov_std)}")

    buyers = valid["user_id"].nunique()
    arppu = gmv / buyers if buyers else 0
    print(f"Покупателей:                          {buyers}")
    print(f"ARPPU (выручка на платящего):        {fmt_money(arppu)}")
    print(f"LTV (средняя выручка на покупателя): {fmt_money(arppu)}")

    per_buyer = valid.groupby("user_id")["order_id"].count()
    avg_orders = per_buyer.mean() if len(per_buyer) else 0
    median_orders = per_buyer.median() if len(per_buyer) else 0
    repeat = (per_buyer >= 2).sum()
    repeat_rate = repeat / len(per_buyer) if len(per_buyer) else 0
    print(f"Среднее заказов на покупателя:      {avg_orders:.2f}")
    print(f"Медиана заказов на покупателя:      {median_orders:.0f}")
    print(f"Повторных покупателей (>=2 заказа): {repeat} ({repeat_rate*100:.1f}%)")

    # LTV медиана (медианная выручка на покупателя)
    ltv_series = valid.groupby("user_id")["amount"].sum()
    ltv_median = ltv_series.median() if len(ltv_series) else 0
    ltv_std = ltv_series.std() if len(ltv_series) else 0
    print(f"LTV медиана:                        {fmt_money(ltv_median)}")
    print(f"LTV std (разброс):                  {fmt_money(ltv_std)}")

    # --- Приток / динамика по месяцам ---
    print("\n" + "=" * 78)
    print("ДИНАМИКА ПО МЕСЯЦАМ (приток)")
    print("=" * 78)
    monthly = valid.groupby("month").agg(
        orders=("order_id", "count"),
        revenue=("amount", "sum"),
        buyers=("user_id", "nunique"),
    ).reset_index()
    monthly["aov"] = monthly["revenue"] / monthly["orders"]

    # Неполные месяцы на границах выборки: май (данные с 05-06) и ноябрь (до 11-02).
    # Их нельзя сравнивать с полными месяцами, поэтому:
    #   - в таблице ДИНАМИКИ и на графике показываем только полные месяцы (июнь–октябрь);
    #   - в итоговых суммах (GMV и пр.) и в когортах май/ноябрь ОСТАВЛЯЕМ — это реальные продажи.
    monthly["partial"] = monthly["month"].isin(
        monthly["month"].iloc[0:1].tolist() +
        monthly["month"].iloc[-1:].tolist()
    )
    monthly.to_csv(os.path.join(OUT, "monthly.csv"), index=False, encoding="utf-8-sig")

    # Таблица динамики — только полные месяцы
    monthly_full = monthly[~monthly["partial"]].reset_index(drop=True)
    print(monthly_full.to_string(index=False))
    monthly_full.to_csv(os.path.join(OUT, "monthly_full.csv"), index=False, encoding="utf-8-sig")
    print("\n  Примечание: май и ноябрь — неполные (границы выборки). "
          "В таблице динамики и на графике они исключены; "
          "в итоговых суммах (GMV, средний чек) и в когортах оставлены как реальные продажи.")

    # --- Гео ---
    print("\n" + "=" * 78)
    print("ТОП ГОРОДОВ")
    print("=" * 78)
    geo = valid[valid["city"].notna() & (valid["city"] != "")].groupby("city").agg(
        orders=("order_id", "count"),
        revenue=("amount", "sum"),
        buyers=("user_id", "nunique"),
    ).reset_index().sort_values("revenue", ascending=False)
    geo["aov"] = geo["revenue"] / geo["orders"]
    geo.to_csv(os.path.join(OUT, "geo.csv"), index=False, encoding="utf-8-sig")
    print(geo.head(12).to_string(index=False))

    # --- Повторные покупки ---
    print("\n" + "=" * 78)
    print("ПОВТОРНЫЕ ПОКУПКИ (заказов на клиента)")
    print("=" * 78)
    dist = per_buyer.value_counts().sort_index()
    dist_df = pd.DataFrame({"orders_per_buyer": dist.index, "clients": dist.values})
    dist_df.to_csv(os.path.join(OUT, "repeat_purchases.csv"), index=False, encoding="utf-8-sig")
    for n, cnt in dist.items():
        print(f"  {n} заказа(ов): {cnt} клиент(ов)")

    # --- Когорты по месяцу первой покупки ---
    print("\n" + "=" * 78)
    print("КОГОРТЫ ПО МЕСЯЦУ ПЕРВОЙ ПОКУПКИ")
    print("=" * 78)
    valid["cohort"] = valid["user_id"].map(valid.groupby("user_id")["created_at"].min().dt.to_period("M"))
    valid["m"] = (valid["created_at"].dt.year - valid["cohort"].dt.year) * 12 + \
                 (valid["created_at"].dt.month - valid["cohort"].dt.month)
    pivot = valid.pivot_table(index="cohort", columns="m", values="order_id",
                              aggfunc="count", fill_value=0)
    pivot.columns = [f"m{int(c)}" for c in pivot.columns]
    pivot.to_csv(os.path.join(OUT, "cohorts.csv"), encoding="utf-8-sig")
    print(pivot.to_string())

    # --- Отмены / проблемы ---
    print("\n" + "=" * 78)
    print("ПРОБЛЕМНЫЕ ЗАКАЗЫ (статусы)")
    print("=" * 78)
    for st, cnt in orders["status"].value_counts().items():
        print(f"  {st:12s} {cnt}")
    pending = orders[orders["status"].isin(["new", "processing"])]
    print(f"  В new/processing (ждать обработки): {len(pending)}")

    # --- Графики (matplotlib) ---
    try:
        import matplotlib
        matplotlib.use("Agg")  # без GUI — сохраняем в PNG
        import matplotlib.pyplot as plt
    except ImportError:
        print("\n[!] matplotlib нет — графики пропущены")
        plt = None

    if plt is not None:
        os.makedirs(OUT, exist_ok=True)

        # 1. Выручка и заказы по месяцам (только полные месяцы)
        mm = monthly_full.copy()
        fig, ax1 = plt.subplots(figsize=(9, 4.5))
        ax1.bar(mm["month"], mm["revenue"], color="#7c3aed", alpha=0.8, label="Выручка")
        ax1.set_ylabel("Выручка, ₽")
        ax1.set_title("Выручка по месяцам (полные месяцы: июнь–октябрь)")
        ax2 = ax1.twinx()
        ax2.plot(mm["month"], mm["orders"], color="#0ea5e9", marker="o", label="Заказы")
        ax2.set_ylabel("Заказы")
        fig.tight_layout()
        fig.savefig(os.path.join(OUT, "chart_monthly_revenue.png"), dpi=110)
        plt.close(fig)

        # 2. Топ городов по выручке
        g = geo.head(10).sort_values("revenue")
        fig, ax = plt.subplots(figsize=(9, 4.5))
        ax.barh(g["city"], g["revenue"], color="#f59e0b", alpha=0.85)
        ax.set_xlabel("Выручка, ₽")
        ax.set_title("Топ городов по выручке")
        fig.tight_layout()
        fig.savefig(os.path.join(OUT, "chart_geo_revenue.png"), dpi=110)
        plt.close(fig)

        # 3. Повторные покупки
        fig, ax = plt.subplots(figsize=(7, 4))
        ax.bar(dist_df["orders_per_buyer"].astype(str), dist_df["clients"],
               color="#10b981", alpha=0.85)
        ax.set_xlabel("Заказов на клиента")
        ax.set_ylabel("Клиентов")
        ax.set_title("Распределение повторных покупок")
        fig.tight_layout()
        fig.savefig(os.path.join(OUT, "chart_repeat.png"), dpi=110)
        plt.close(fig)

        print("\nГрафики сохранены:", [f for f in os.listdir(OUT) if f.startswith("chart_")])

    print("\nГотово. CSV в:", os.path.abspath(OUT))


if __name__ == "__main__":
    main()