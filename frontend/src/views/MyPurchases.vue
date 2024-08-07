<script setup>
import {reactive} from "vue";
import apiClient from "@/api/index.js";
import ViewBlock from "@/components/ViewBlock.vue";
import CommonButton from "@/components/CommonButton.vue";
import PrettyInput from "@/components/PrettyInput.vue";

const purchases_form = reactive({
  email: ''
});

async function sendLinks() {
  try {
    const response = await apiClient.post('/send-links/', {
      email: purchases_form.email,
      captcha: purchases_form.captcha
    });

    if (response.status === 200)
      window.location.href = '/';
  } catch (error) {
    console.error(error);
  }
}
</script>

<template>
  <ViewBlock>
    <template #title>{{ $t('routes.my_purchases') }}</template>
    <form class="get-files-form" method="post" @submit.prevent="sendLinks">
      <span>{{ $t('purchases.email.ask') }}:</span>
      <pretty-input name="email" type="email" v-model="purchases_form.email" :placeholder="$t('purchases.email.placeholder')"/>
      <common-button tabindex="0">{{ $t('buttons.send_links') }}</common-button>
    </form>
  </ViewBlock>
</template>

<style scoped lang="scss">
.get-files-form {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 15px;
  font-size: 16px;
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