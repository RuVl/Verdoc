# Инцидент: заказ с OrderItem 652 — оплачен, но ссылки не пришли и не восстанавливаются

**Дата:** 2026-07-28 (оплата с задержкой ~2ч ночью, инцидент обнаружен 2026-07-28 вечером через `/api/send-links/`)

## Симптом

Клиент создал заказ и оплатил его сразу, но callback от Plisio дошёл до сайта с задержкой ~2 часа (обычная задержка подтверждения крипто-транзакции). Письмо со ссылками на скачивание не пришло. Повторный запрос ссылок через форму `/purchases` (`SendDownloadLinksView`, `backend/order/views.py:196`) стабильно падает 500:

```
[WARNING] [order.views] Not enough download links for order item 652
[ERROR] [django.request] Internal Server Error: /api/send-links/
...
File "/app/order/views.py", line 250, in get_order_item_links
    raise ValueError(f"Not enough download links for order item {order_item.id}")
ValueError: Not enough download links for order item 652
```

## Root cause

`Passport.reserve()` / `Passport.sell()` (`backend/passport/models.py`, до фикса) выбирали файлы запросом **"первые N файлов со статусом RESERVED/IN_STOCK"** без привязки к конкретному `OrderItem` — это ровно та проблема, что уже была описана в заметке по рефакторингу БД (`docs/db-refactoring/option-1-atomic-link.md`, раздел "NOW"): пока `DownloadLink` не создана, невозможно понять, какой файл зарезервирован для какого заказа.

Из-за этого при **параллельной обработке двух callback'ов на один и тот же `Passport`** (например, оплата этого клиента и другого покупателя того же паспорта пришли почти одновременно) оба вызова `Passport.sell(count)` без блокировки строк могли прочитать **одно и то же множество `RESERVED`-файлов**, ещё не закоммиченное друг другом:

1. Оба вызова помечают одни и те же файлы `SOLD` (избыточно, но не страшно само по себе).
2. Оба пытаются создать `DownloadLink(passport_file=<тот же файл>)` — а `DownloadLink.passport_file` это `OneToOneField` с уникальным ограничением в БД → второй `create()` падает `IntegrityError`.
3. Эта ошибка вылетает из `OrderItem.sell()` (обёрнут в `@atomic`) — транзакция для **проигравшего** заказа откатывается: его файлы остаются `RESERVED`, `is_reserved` остаётся `True`.
4. НО: `Order.status = PAID` уже был сохранён **отдельной, уже закоммиченной** транзакцией в `PlisioCallbackView.update_order_status()` **до** вызова `order.sell()` — откат `sell()` эту запись не затрагивает.
5. Итог: заказ навсегда завис в состоянии `status=PAID`, `is_reserved=True`, `DownloadLink` не создана, писем нет.
6. При повторном запросе через `/api/send-links/`: `SendDownloadLinksView` находит заказ по `status=PAID`, видит 0 `DownloadLink`, пытается восстановить их fallback-запросом `PassportFile.objects.filter(passport=..., status=SOLD, downloadlink__isnull=True)` — но файлы этого заказа всё ещё `RESERVED`, а не `SOLD`, поэтому fallback ничего не находит → тот же `ValueError`.

Задержка оплаты в 2 часа сама по себе не является причиной (наш `expire_transactions` — cron `5 0 * * *`, т.е. раз в сутки — за это окно не срабатывал бы). Она лишь совпала по времени с обработкой параллельного заказа; корневая причина — отсутствие блокировки строк и привязки файла к конкретному `OrderItem` при `reserve`/`sell`.

## Исправление (применено в этой сессии, ветка `hotfix/plisio-callback-race`)

1. **`backend/passport/models.py`** — `Passport.reserve/return2stock/sell` теперь используют `select_for_update()` на выбираемых файлах внутри `@atomic`. Конкурентный вызов блокируется до коммита первого, после чего повторно видит актуальные статусы — гонка из п.1-2 больше невозможна.
2. **`backend/order/views.py`** — `PlisioCallbackView.post()`: обновление статуса заказа (`update_order_status`) и `order.sell()`/`order.reset_reservation()` теперь выполняются **в одной транзакции**. Если `sell()` падает (`ValueError` — например, повторный/дублирующийся callback на уже проданный заказ), откатывается **всё**, включая `status`, — заказ остаётся в прежнем состоянии и safe для повторной обработки Plisio-ретраем, вместо зависания в "PAID без файлов". Ответ на конфликт — `409 Conflict` вместо неотловленного 500.
3. Регресс-тест: `backend/order/tests.py::PlisioCallbackIdempotencyTests` — дублирующийся `completed`-callback на один заказ не крашится и не создаёт лишних `DownloadLink`.

Это **не устраняет** первопричину полностью (файл всё ещё не привязан персонально к `OrderItem` до продажи — читай `docs/db-refactoring/option-1-atomic-link.md`), но закрывает конкретный гоночный сценарий, который привёл к инциденту, и превращает будущие похожие сбои в безопасный retry вместо зависшего заказа.

## Ручное восстановление для пострадавшего клиента (выполнить на проде)

Я не имею доступа к продовой БД из этой сессии (прод — отдельный сервер, `CLAUDE.md`) — команды ниже нужно выполнить самостоятельно через `make manage c="shell"` (или `manage.py shell` в контейнере) на проде. Сначала только диагностика (read-only):

```python
from order.models import Order, OrderItem, DownloadLink
from passport.models import PassportFile

item = OrderItem.objects.select_related("order", "passport").get(id=652)
print(item.order.id, item.order.status, item.is_reserved, item.quantity)
print(list(item.passport.files.filter(status=PassportFile.PassportFileStatus.RESERVED).values_list("id", "file_path")))
print(list(DownloadLink.objects.filter(order_item=item).values_list("id", "uuid")))
```

Если `item.is_reserved == True` и `status=PAID` (ожидаемая картина по анализу выше) — файлы физически всё ещё зарезервированы за этим заказом, продажу можно провести вручную:

```python
from order.utils import send_download_links

links = item.sell()  # теперь безопасно: select_for_update больше не даст гонки
send_download_links(None, links, item.order.user_email)  # request=None -> используйте реальный request или соберите ссылку вручную, если get_link требует request
```

`DownloadLink.get_link()` использует `Site.objects.get_current(request)` — если `request=None` не сработает в вашей версии, соберите ссылку вручную: `f"https://{domain}/api/order/file/{item.order.user_email}/{link.uuid}/"`, где `domain` — текущий рабочий домен (`verif-docs.com`/зеркало).

Если диагностика покажет **другую** картину (например, `is_reserved=False`, но файлы уже `SOLD` за кем-то ещё) — до применения любых write-команд стоит сверить это со мной или вручную выделить клиенту компенсирующий файл того же паспорта (если в наличии) и оформить возврат/докупку по усмотрению.

## Дальнейшие шаги

- Долгосрочное решение — реализовать **Вариант 1 (Atomic Link)** из `docs/db-refactoring/option-1-atomic-link.md` (привязка `reserved_for_item_id` прямо на `PassportFile`), по плану миграции в `docs/db-refactoring/data-migration-plan.md`.
- Отдельно стоит пересмотреть частоту `expire_transactions` (сейчас `5 0 * * *` — раз в сутки, при этом `Order.is_expired()` считает истечение через ~1 час) — несоответствие каденции cron'а и порога истечения обсудить отдельно, вне рамок этого инцидента.
