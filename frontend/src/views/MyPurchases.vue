<script setup>
import {ref} from "vue";
import apiClient from "@/api/index.js";
// import VueRecaptcha from 'vue-recaptcha';
import ViewBlock from "@/components/ViewBlock.vue";
import CommonButton from "@/components/CommonButton.vue";
import PrettyInput from "@/components/PrettyInput.vue";

const email = ref('');
const captcha = ref(null);

async function sendLinks() {
  try {
    const response = await apiClient.post('/api/send-links/', {
      email: email,
      recaptcha_token: captcha,
    });
    alert('Links have been sent to your email!');
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
      <pretty-input name="email" type="email" v-model="email" :placeholder="$t('purchases.email.placeholder')"/>
      <common-button tabindex="0">{{ $t('buttons.send_links') }}</common-button>
      <!--<vue-recaptcha @verify="(token) => captcha = token" @expired="captcha=null" sitekey="6LejCywnAAAAALn7R9dQPhATiwmNCpHELH9XzKAu"/>-->
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