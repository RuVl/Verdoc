<script setup>
import ViewBlock from "@/components/ViewBlock.vue";
import CommonButton from "@/components/CommonButton.vue";
import InputWrapper from "@/components/InputWrapper.vue";
</script>

<template>
  <ViewBlock>
    <template #title>{{ $t('routes.my_purchases') }}</template>
    <form class="get-files-form" method="post">
      <span>{{ $t('purchases.email.ask') }}:</span>
      <div class="in-row">
        <InputWrapper>
          <input name="email" type="email" :placeholder="$t('purchases.email.placeholder')">
        </InputWrapper>
        <CommonButton tabindex="0">{{ $t('buttons.send_links') }}</CommonButton>
      </div>
      TODO: reCAPTCHA
    </form>
  </ViewBlock>
</template>

<style scoped lang="scss">
.get-files-form {
  .in-row {
    width: max-content;
    margin: 30px 0 15px 0;

    display: flex;
    gap: 15px;
    flex-direction: row;
    align-items: stretch;
  }
}
</style>