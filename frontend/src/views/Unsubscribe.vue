<script setup>
import {onMounted, ref} from "vue";
import {useRoute} from "vue-router";
import apiClient from "@/api/index.js";
import ViewBlock from "@/components/ViewBlock.vue";
import CommonButton from "@/components/CommonButton.vue";

const route = useRoute();
const token = route.params.token;

const loading = ref(true);
const invalid = ref(false);
const email = ref('');

// POST, not a link the mail client can follow: Gmail and Outlook pre-fetch every URL in a
// message, so opting out on GET would unsubscribe people who never clicked.
async function unsubscribe() {
  try {
    const response = await apiClient.post(`/unsubscribe/${token}/`);
    email.value = response.data.email;
  } catch (error) {
    if (error.response?.status === 400) invalid.value = true;
    else console.error('Error unsubscribing:', error);
  } finally {
    loading.value = false;
  }
}

onMounted(unsubscribe);
</script>

<template>
  <ViewBlock>
    <template #title>{{ $t('routes.unsubscribe') }}</template>

    <p v-if="loading" class="notice">{{ $t('unsubscribe.loading') }}</p>

    <div v-else-if="invalid" class="notice failed">
      <p>{{ $t('unsubscribe.invalid_link') }}</p>
      <CommonButton href="/">{{ $t('buttons.go_back_home') }}</CommonButton>
    </div>

    <div v-else-if="!email" class="notice failed">
      <p>{{ $t('unsubscribe.error') }}</p>
      <CommonButton href="/">{{ $t('buttons.go_back_home') }}</CommonButton>
    </div>

    <div v-else class="notice done">
      <p>{{ $t('unsubscribe.done', {email: email}) }}</p>
      <CommonButton href="/">{{ $t('buttons.go_back_home') }}</CommonButton>
    </div>
  </ViewBlock>
</template>

<style lang="scss" scoped>
.notice {
  font-size: 16px;
  line-height: 24px;
}

.notice.done, .notice.failed {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 20px;
}

@media screen and (max-width: 480px) {
  .notice {
    font-size: 14px;
    text-align: center;
  }

  .notice.done, .notice.failed {
    align-items: center;
  }
}
</style>
