<script setup>
import {computed, onMounted, ref} from "vue";
import {useRoute} from "vue-router";
import {useI18n} from "vue-i18n";
import apiClient from "@/api/index.js";
import ViewBlock from "@/components/ViewBlock.vue";
import CommonButton from "@/components/CommonButton.vue";
import ProductsList from "@/components/ListView.vue";
import IconDownload from "@/components/icons/IconDownload.vue";
import IconRefresh from "@/components/icons/IconRefresh.vue";
import IconCopy from "@/components/icons/IconCopy.vue";

const route = useRoute();
const token = route.params.token;
const {locale} = useI18n();

const loading = ref(true);
const gone = ref(false);
const email = ref('');
const orders = ref([]);
const copied = ref(null);

// Every allocation of every item, so "refresh all" can patch them in one pass.
const allocations = computed(() => orders.value.flatMap(order => order.items.flatMap(item => item.allocations)));

function apply(fresh) {
  const target = allocations.value.find(allocation => allocation.id === fresh.id);
  if (target) Object.assign(target, fresh);
}

async function fetchPurchases() {
  loading.value = true;
  try {
    const response = await apiClient.get(`/purchases/${token}/`);
    email.value = response.data.email;
    orders.value = response.data.orders;
  } catch (error) {
    // 404 is the only expected answer here and means the page token is spent, see ADR-0004.
    if (error.response?.status === 404) gone.value = true;
    else console.error('Error fetching purchases:', error);
  } finally {
    loading.value = false;
  }
}

async function refresh(allocation) {
  try {
    const response = await apiClient.post(`/purchases/${token}/refresh/${allocation.id}/`);
    apply(response.data);
  } catch (error) {
    if (error.response?.status === 404) gone.value = true;
    else console.error('Error refreshing the link:', error);
  }
}

async function refreshAll() {
  try {
    const response = await apiClient.post(`/purchases/${token}/refresh-all/`);
    response.data.forEach(apply);
  } catch (error) {
    if (error.response?.status === 404) gone.value = true;
    else console.error('Error refreshing the links:', error);
  }
}

async function copyLink(allocation) {
  try {
    await navigator.clipboard.writeText(allocation.download_url);
    copied.value = allocation.id;
    setTimeout(() => {
      if (copied.value === allocation.id) copied.value = null;
    }, 2000);
  } catch (error) {
    console.error('Error copying the link:', error);
  }
}

// "4 августа 2026, 16:34" instead of the locale's raw numeric default.
function formatDate(value) {
  if (!value) return '';
  return new Date(value).toLocaleString(locale.value, {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function formatPrice(item) {
  return `${parseFloat(item.unit_price).toFixed(2)} ${item.unit_price_currency}`;
}

onMounted(fetchPurchases);
</script>

<template>
  <ViewBlock>
    <template #title>{{ $t('routes.my_purchases') }}</template>

    <p v-if="loading" class="notice">{{ $t('purchases.page.loading') }}</p>

    <div v-else-if="gone" class="notice gone">
      <p>{{ $t('purchases.page.expired_link') }}</p>
      <CommonButton href="/purchases">{{ $t('buttons.request_new_link') }}</CommonButton>
    </div>

    <p v-else-if="!orders.length" class="notice">{{ $t('purchases.page.empty') }}</p>

    <template v-else>
      <p class="share-warning">{{ $t('purchases.page.share_warning') }}</p>

      <div class="page-controls">
        <span class="owner-email">{{ email }}</span>
        <CommonButton @click="refreshAll">{{ $t('buttons.refresh_all_links') }}</CommonButton>
      </div>

      <ProductsList v-for="order in orders" :key="order.id" :elements="order.items">
        <template #title>
          <span class="order-date">{{ formatDate(order.paid_at || order.created_at) }}</span>
        </template>
        <template #default="{element: item}">
          <span class="product-name">{{ item.product_name }}</span>
          <span class="unit-price">{{ formatPrice(item) }}</span>

          <ul class="files">
            <li v-for="(allocation, index) in item.allocations" :key="allocation.id" class="file">
              <!-- Name and expiry wrap together, so the icons never end up looking like they
                   belong to the next file. -->
              <span class="file-info">
                <span class="file-name">{{ $t('purchases.page.file', {n: index + 1}) }}</span>

                <span v-if="allocation.is_downloadable" class="file-expiry">
                  {{ $t('purchases.page.valid_until', {date: formatDate(allocation.expires_at)}) }}
                </span>
                <span v-else class="file-expiry expired">{{ $t('purchases.page.file_expired') }}</span>
              </span>

              <!-- Icon-only, so the row stays readable on a phone; the label lives in the tooltip. -->
              <span class="file-actions">
                <a v-if="allocation.is_downloadable" :href="allocation.download_url"
                   :title="$t('buttons.download')" class="icon-btn">
                  <IconDownload/>
                </a>
                <span v-else :title="$t('purchases.page.file_expired')" class="icon-btn disabled">
                  <IconDownload/>
                </span>

                <!-- Kept in place while disabled, so the icons of every file stay in one column. -->
                <button :class="{copied: copied === allocation.id, disabled: !allocation.is_downloadable}"
                        :title="copied === allocation.id ? $t('buttons.copied') : $t('buttons.copy_link')"
                        class="icon-btn" type="button" @click="copyLink(allocation)">
                  <IconCopy/>
                </button>

                <button :title="$t('buttons.refresh_link')" class="icon-btn" type="button"
                        @click="refresh(allocation)">
                  <IconRefresh/>
                </button>
              </span>
            </li>
          </ul>
        </template>
      </ProductsList>
    </template>
  </ViewBlock>
</template>

<style lang="scss" scoped>
.notice {
  font-size: 16px;
  line-height: 24px;
}

.notice.gone {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 20px;
}

.share-warning {
  font-size: 16px;
  font-weight: 600;
  line-height: 24px;
  color: #d92d20;
  margin-bottom: 20px;
}

.page-controls {
  display: flex;
  align-items: center;
  gap: 25px;
  margin-bottom: 10px;

  .owner-email {
    font-size: 14px;
    font-weight: 600;
    overflow-wrap: anywhere;
  }

  > *:last-child {
    margin-left: auto;
    text-wrap: nowrap;
  }
}

.order-date {
  font-size: 16px;
  font-weight: 600;
}

// One row per bought position: name and price on top, its files underneath.
:deep(.products-list > ul > li) {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 10px 25px;
}

.product-name {
  white-space: normal;
  overflow-wrap: anywhere;
  text-wrap: pretty;
}

.unit-price {
  justify-self: end;
}

.files {
  grid-column: 1 / -1;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 0;
  margin: 5px 0 0 0;

  .file {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px 20px;
    list-style: none;
    font-weight: 500;
  }

  .file-info {
    display: flex;
    align-items: baseline;
    flex-wrap: wrap;
    gap: 2px 20px;
    min-width: 0;
  }

  .file-name {
    min-width: 80px;
  }

  .file-expiry {
    font-size: 12px;
    font-weight: 400;
    color: var(--second-color-text);
    white-space: normal;
  }

  .file-expiry.expired {
    color: #d92d20;
    font-weight: 500;
  }

  .file-actions {
    display: flex;
    align-items: center;
    gap: 18px;
    margin-left: auto;
  }
}

.icon-btn {
  border: none;
  background: none;
  padding: 0;
  line-height: 0;
  color: var(--accent-color);

  &:hover {
    cursor: pointer;
    opacity: .7;
  }
}

.icon-btn.disabled {
  color: var(--second-color-text);
  pointer-events: none;
}

// Momentary confirmation for a button whose label is only a tooltip.
.icon-btn.copied {
  color: #12a150;
}

@media screen and (max-width: 768px) {
  .page-controls {
    flex-direction: column;
    align-items: flex-start;
    gap: 15px;

    > *:last-child {
      margin-left: 0;
      align-self: stretch;
      text-align: center;
    }
  }

}

@media screen and (max-width: 480px) {
  .notice {
    font-size: 14px;
    text-align: center;
  }

  .notice.gone {
    align-items: center;
  }

  :deep(.products-list > ul > li) {
    gap: 10px 15px;
  }

  .files .file {
    gap: 5px 15px;
  }

  .share-warning {
    font-size: 14px;
    text-align: center;
  }

  .files .file-actions {
    gap: 15px;
  }
}
</style>
