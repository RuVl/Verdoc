<script setup>
import logo_icon from '@/assets/logo_icon.png'
</script>

<template>
  <router-link class="logo-link" :to="{name: 'main'}">
    <div class="logo-icon">
      <img :src="logo_icon" alt="logo">
      <div class="circle"></div>
    </div>
    <div class="site-info">
      <span class="name">Verif-<span style="color: var(--accent-color)">docs</span></span>
      <br>
      <span class="description">{{ $t('site_info.logo_description') }}</span>
    </div>
  </router-link>
</template>

<style lang="scss" scoped>
.logo-wrapper {
  display: flex;
  align-items: center;
}

.logo-link {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 25px;
  width: fit-content;
  text-decoration: none;

  &:active, &:visited {
    color: initial;
  }

  &:hover {
    opacity: .85;
  }
}

.logo-icon {
  --size: 44px;

  position: relative;
  height: calc(var(--size) + 4px);
  width: var(--size);

  > img {
    width: 100%;
    height: 100%;
    object-fit: fill;
  }

  > .circle {
    position: absolute;
    bottom: 0;
    z-index: -1;
    background-color: var(--accent-color);

    width: var(--size);
    height: var(--size);
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

@media only screen and (max-width: 350px) {
  .logo-link {
    gap: 15px;

    .logo-icon {
      --size: 35px;
    }
  }

  .site-info {
    > .description {
      font-size: 10px;
    }

    > .name {
      font-size: 16px;
    }
  }
}
</style>