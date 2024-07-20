<script setup>
import logo_icon from '@/assets/logo_icon.png'
</script>

<template>
  <router-link class="logo-wrapper" :to="{name: 'main'}">
    <div class="logo_icon">
      <img :src="logo_icon" alt="logo">
      <div class="circle"></div>
    </div>
    <div class="site-info">
      <span class="name">Verif-<span style="color: var(--accent-color)">docs</span></span>
      <br>
      <span class="description">{{ $t('site_info.logo_description')}}</span>
    </div>
  </router-link>
</template>

<style lang="scss" scoped>
.logo-wrapper {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 25px;
  text-decoration: none;

  &:active, &:visited {
    color: initial;
  }

  &:hover {
    opacity: .85;
  }
}

.logo_icon {
  position: relative;
  height: 48px;
  width: 44px;

  > .circle {
    position: absolute;
    bottom: 0;
    z-index: -1;
    background-color: var(--accent-color);

    width: 44px;
    height: 44px;
    border-radius: 100%;
  }
}

.site-info {
  text-wrap: nowrap;

  > .name {
    font-size: 20px;
    font-weight: 600;
    float: left;
    text-transform: uppercase;
  }

  > .description {
    font-size: 12px;
    float: left;
  }
}
</style>