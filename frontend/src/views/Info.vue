<script setup>
import ViewBlock from "@/components/ViewBlock.vue";
</script>

<template>
  <ViewBlock class="info-block">
    <template #title>{{ $t('routes.info') }}</template>

    <h4>{{ $t('site_info.rules.1.title') }}</h4>
    <p>{{ $t('site_info.rules.1.text') }}</p>

    <h4>{{ $t('site_info.rules.2.title') }}</h4>
    <p>{{ $t('site_info.rules.2.text') }}</p>

    <h4>{{ $t('site_info.rules.3.title') }}</h4>
    <p>{{ $t('site_info.rules.3.text') }}</p>

    <h4>{{ $t('site_info.rules.4.title') }}</h4>
    <p>{{ $t('site_info.rules.4.text') }}</p>

    <h4>{{ $t('site_info.rules.5.title') }}</h4>
    <p>{{ $t('site_info.rules.5.text') }}</p>

    <h4>{{ $t('site_info.rules.6.title') }}</h4>
    <p>{{ $t('site_info.rules.6.text') }}</p>
  </ViewBlock>
</template>

<style scoped lang="scss">
.info-block {
  p:not(:last-child) {
    margin-bottom: 20px;
  }

  h4 {
    margin-bottom: 10px;
    font-weight: 600;
  }

  p {
    margin-left: 15px;
    white-space: pre-line;
    line-height: 1.5em;
  }
}
</style>