"""PoC: 호스트 Dagster → kind SparkApplication 제출·폴링 리소스.

`dagster-k8s`의 `K8sRunLauncher`는 Dagster를 클러스터 내부에 배포할 때의 옵션이라
본 토폴로지(호스트 Dagster)엔 맞지 않는다. 여기서는 kubernetes 클라이언트로
Spark Operator의 `SparkApplication`(CRD)을 직접 제출하고 상태를 폴링한다.
"""

import time

from kubernetes import client, config
from kubernetes.client.exceptions import ApiException

import dagster as dg
from dagster_project.defs.poc.constants import (
    CRD_GROUP,
    CRD_PLURAL,
    CRD_VERSION,
)


class SparkOperatorResource(dg.ConfigurableResource):
    """kind 클러스터의 SparkApplication을 제출하고 종료까지 폴링한다(호스트 실행)."""

    kube_context: str
    namespace: str = "default"
    poll_interval_s: int = 5
    timeout_s: int = 900

    def _custom_api(self) -> client.CustomObjectsApi:
        # 호스트 kubeconfig의 지정 컨텍스트로 접속
        config.load_kube_config(context=self.kube_context)
        return client.CustomObjectsApi()

    def _core_api(self) -> client.CoreV1Api:
        config.load_kube_config(context=self.kube_context)
        return client.CoreV1Api()

    def _delete_if_exists(self, co: client.CustomObjectsApi, name: str) -> None:
        # 동일 이름 잔여 오브젝트 제거 후 404까지 대기(멱등 재제출)
        try:
            co.delete_namespaced_custom_object(
                CRD_GROUP, CRD_VERSION, self.namespace, CRD_PLURAL, name
            )
        except ApiException as exc:
            if exc.status != 404:
                raise
        for _ in range(60):
            try:
                co.get_namespaced_custom_object(
                    CRD_GROUP, CRD_VERSION, self.namespace, CRD_PLURAL, name
                )
            except ApiException as exc:
                if exc.status == 404:
                    return
            time.sleep(2)

    def submit_and_wait(self, manifest: dict) -> tuple[str, str]:
        """SparkApplication을 제출하고 종료 상태·driver 로그를 반환한다."""
        co = self._custom_api()
        name = manifest["metadata"]["name"]
        self._delete_if_exists(co, name)
        co.create_namespaced_custom_object(
            CRD_GROUP, CRD_VERSION, self.namespace, CRD_PLURAL, manifest
        )

        terminal = {"COMPLETED", "FAILED", "FAILING", "INVALIDATING"}
        state = ""
        waited = 0
        while waited < self.timeout_s:
            obj = co.get_namespaced_custom_object(
                CRD_GROUP, CRD_VERSION, self.namespace, CRD_PLURAL, name
            )
            state = obj.get("status", {}).get("applicationState", {}).get("state", "")
            if state in terminal:
                break
            time.sleep(self.poll_interval_s)
            waited += self.poll_interval_s

        return state, self._driver_logs(f"{name}-driver")

    def _driver_logs(self, driver_pod: str) -> str:
        try:
            return self._core_api().read_namespaced_pod_log(driver_pod, self.namespace)
        except ApiException:
            return ""
