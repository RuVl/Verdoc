<script setup>
import Block from "@/components/Block.vue";
import PathNav from "@/components/PathNav.vue";
</script>

<template>
  <Block class="view-block">
    <PathNav/>
    <h2 class="title"><slot name="title"/></h2>
    <slot/>
  </Block>
</template>

<style scoped lang="scss">
.view-block {
  & > .title {
    margin: 20px 0;
  }
}
</style>