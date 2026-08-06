<script setup>
import {onMounted, ref} from "vue";
import {useRoute} from "vue-router";
import apiClient from "@/api/index.js";
import ViewBlock from "@/components/ViewBlock.vue";
import CommonButton from "@/components/CommonButton.vue";

const route = useRoute();
const token = route.params.token;

const loading = ref(true);
const submitting = ref(false);
const invalid = ref(false);
const failed = ref(false);
// Whether the token was actually read. Without it a failed load would fall through to the
// "already unsubscribed" branch and tell the customer something that is not true.
const resolved = ref(false);
const email = ref('');
const subscribed = ref(false);
const done = ref(false);

// Reading the token is a GET and changes nothing: opening the link out of curiosity - or having
// a mail scanner pre-fetch it - must not cost anyone the mailing list. The POST below is the
// only thing that opts out, and it takes a click.
async function resolveToken() {
  loading.value = true;
  failed.value = false;
  try {
    const response = await apiClient.get(`/unsubscribe/${token}/`);
    email.value = response.data.email;
    subscribed.value = response.data.is_subscribed;
    resolved.value = true;
  } catch (error) {
    if (error.response?.status === 400) invalid.value = true;
    else {
      failed.value = true;
      console.error('Error reading the unsubscribe link:', error);
    }
  } finally {
    loading.value = false;
  }
}

async function unsubscribe() {
  submitting.value = true;
  failed.value = false;
  try {
    const response = await apiClient.post(`/unsubscribe/${token}/`);
    email.value = response.data.email;
    subscribed.value = false;
    done.value = true;
  } catch (error) {
    if (error.response?.status === 400) invalid.value = true;
    else {
      failed.value = true;
      console.error('Error unsubscribing:', error);
    }
  } finally {
    submitting.value = false;
  }
}

onMounted(resolveToken);
</script>

<template>
  <ViewBlock>
    <template #title>{{ $t('routes.unsubscribe') }}</template>

    <p v-if="loading" class="notice">{{ $t('unsubscribe.loading') }}</p>

    <div v-else-if="invalid" class="notice state">
      <p>{{ $t('unsubscribe.invalid_link') }}</p>
      <CommonButton href="/">{{ $t('buttons.go_back_home') }}</CommonButton>
    </div>

    <div v-else-if="done" class="notice state">
      <p>{{ $t('unsubscribe.done', {email: email}) }}</p>
      <CommonButton href="/">{{ $t('buttons.go_back_home') }}</CommonButton>
    </div>

    <div v-else-if="!resolved" class="notice state">
      <p class="error">{{ $t('unsubscribe.unreachable') }}</p>
      <CommonButton type="button" @click="resolveToken">{{ $t('buttons.retry') }}</CommonButton>
    </div>

    <div v-else-if="!subscribed" class="notice state">
      <p>{{ $t('unsubscribe.already', {email: email}) }}</p>
      <CommonButton href="/">{{ $t('buttons.go_back_home') }}</CommonButton>
    </div>

    <div v-else class="notice state">
      <p>{{ $t('unsubscribe.confirm', {email: email}) }}</p>
      <p v-if="failed" class="error">{{ $t('unsubscribe.error') }}</p>
      <div class="actions">
        <CommonButton :disabled="submitting" type="button" @click="unsubscribe">
          {{ submitting ? $t('unsubscribe.submitting') : $t('buttons.unsubscribe') }}
        </CommonButton>
        <a class="cancel" href="/">{{ $t('buttons.stay_subscribed') }}</a>
      </div>
    </div>
  </ViewBlock>
</template>

<style lang="scss" scoped>
.notice {
  font-size: 16px;
  line-height: 24px;
}

.notice.state {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 20px;
}

.error {
  color: #d92d20;
  font-weight: 600;
}

.actions {
  display: flex;
  align-items: center;
  gap: 25px;
}

.cancel {
  color: var(--second-color-text);
  font-size: 14px;
  text-decoration: none;

  &:hover {
    opacity: .7;
  }
}

@media screen and (max-width: 480px) {
  .notice {
    font-size: 14px;
    text-align: center;
  }

  .notice.state {
    align-items: center;
  }

  .actions {
    flex-direction: column;
    gap: 15px;
  }
}
</style>
