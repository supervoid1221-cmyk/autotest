<template>
  <div>
    <n-card :bordered="false" class="mt-4 proCard" title="修改账号密码">
      <n-grid cols="1 s:1 m:3 l:3 xl:3 2xl:3" responsive="screen">
        <n-grid-item offset="0 s:0 m:1 l:1 xl:1 2xl:1">
          <n-form
            :label-width="80"
            :model="formValue"
            :rules="rules"
            label-placement="left"
            ref="formRef"
            class="py-8"
          >
            <n-form-item label="新密码" path="new_password">
              <n-input
                v-model:value="formValue.new_password"
                placeholder="输入新密码"
                type="password"
              />
            </n-form-item>
            <n-form-item label="确认密码" path="confirm_password">
              <n-input
                v-model:value="formValue.confirm_password"
                placeholder="输入确认密码"
                type="password"
              />
            </n-form-item>

            <div style="margin-left: 80px">
              <n-space>
                <n-button type="primary" @click="formSubmit">提交</n-button>
                <n-button @click="resetForm">重置</n-button>
              </n-space>
            </div>
          </n-form>
        </n-grid-item>
      </n-grid>
    </n-card>
  </div>
</template>

<script lang="ts" setup>
  import { ref, unref, reactive } from 'vue';
  import { useMessage } from 'naive-ui';
  import { reset_password } from '@/api/account/http';
  import { useSubmitRedirect } from '@/hooks/web/useSubmitRedirect';
  import { ResetPass } from '@/api/account/models';

  const rules = {
    // 校验表单
    new_password: {
      required: true,
      message: '输入新密码',
      trigger: 'blur',
    },
    confirm_password: {
      required: true,
      message: '输入确认密码',
      trigger: 'blur',
    },
  };

  const formRef: any = ref(null);
  const message = useMessage();
  const { redirectAfterSubmit } = useSubmitRedirect();

  let defaultValue = {
    // 表单默认值，变量可以修改
    new_password: '',
    confirm_password: '',
  };

  const defaultValueRef = () => defaultValue;

  let formValue = reactive(defaultValueRef()); // 表单显示的数据

  function formSubmit() {
    formRef.value.validate(async (errors) => {
      if (!errors) {
        const data = {
          new_password: formValue.new_password,
          confirm_password: formValue.confirm_password,
        };

        await reset_password(data as ResetPass);
        message.success('提交成功');
        redirectAfterSubmit({ name: 'project_project' });
      } else {
        message.error('验证失败，请填写完整信息');
      }
    });
  }

  function resetForm() {
    formRef.value.restoreValidation();
    formValue = Object.assign(unref(formValue), defaultValueRef()); //用新的默认值，修改原有变量
  }
</script>
