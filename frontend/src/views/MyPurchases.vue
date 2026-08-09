<script setup>
import {reactive, ref} from "vue";
import apiClient from "@/api/index.js";
import {useSettingsStore} from "@/stores/settings";
import {errorMessageKey} from "@/api/errors.js";
import ViewBlock from "@/components/ViewBlock.vue";
import CommonButton from "@/components/CommonButton.vue";
import PrettyInput from "@/components/PrettyInput.vue";

const purchases_form = reactive({
  email: ''
});

const error = ref(null);
const sending = ref(false);

async function sendLinks() {
  error.value = null;
  sending.value = true;
  try {
    const response = await apiClient.post('/send-links/', {
      email: purchases_form.email,
      language: useSettingsStore().currentLanguage,
    });

    if (response.status === 200)
      window.location.href = '/';
  } catch (e) {
    // 404 is "no paid orders on this address" and 502 is "the mail did not go out" - the customer
    // has to do something different in each case, so they must not look the same.
    error.value = errorMessageKey(e, {
      404: 'purchases.email.error.not_found',
      502: 'purchases.email.error.mail_failed',
    });
    console.error('Cannot send the purchases link:', e);
  } finally {
    sending.value = false;
  }
}
</script>

<template>
  <ViewBlock>
    <template #title>{{ $t('routes.my_purchases') }}</template>
    <form class="get-files-form" method="post" @submit.prevent="sendLinks">
      <span>{{ $t('purchases.email.ask') }}:</span>
      <pretty-input v-model="purchases_form.email" :placeholder="$t('purchases.email.placeholder')" name="email"
                    type="email"/>
      <p v-if="error" class="form-error">{{ $t(error) }}</p>
      <common-button :disabled="sending" tabindex="0">{{ $t('buttons.send_links') }}</common-button>
    </form>
  </ViewBlock>
</template>

<style lang="scss" scoped>
.get-files-form {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 15px;
  font-size: 16px;

  .form-error {
    color: var(--red-color);
    margin: 0;
  }
}

@media screen and (max-width: 480px) {
  .get-files-form {
    align-items: center;
    gap: 15px;
    font-size: 14px;

    > span {
      text-align: center;
    }
  }
}
</style>