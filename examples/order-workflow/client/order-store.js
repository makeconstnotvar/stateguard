import { makeAutoObservable, runInAction } from "mobx";

export class OrderStore {
  remote = { kind: "idle" };
  operation = { kind: "idle" };
  requestSequence = 0;

  constructor(api) {
    this.api = api;
    makeAutoObservable(this, { api: false }, { autoBind: true });
  }

  applyAuthoritativeSnapshot(order) {
    const currentVersion = this.remote.kind === "ready" ? Number(this.remote.order.version) : 0;
    if (Number(order.version) < currentVersion) {
      return false;
    }
    this.remote = { kind: "ready", order };
    return true;
  }

  async submit() {
    if (this.remote.kind !== "ready") {
      return { kind: "rejected", reason: "not_ready" };
    }

    const requestId = ++this.requestSequence;
    const snapshot = this.remote.order;
    this.operation = { kind: "submitting", requestId };

    const result = await this.api.submitOrder({
      orderId: snapshot.id,
      expectedVersion: Number(snapshot.version),
    });

    runInAction(() => {
      if (requestId !== this.requestSequence) {
        return;
      }
      if (result.kind === "accepted") {
        this.applyAuthoritativeSnapshot(result.order);
        this.operation = { kind: "idle" };
        return;
      }
      this.operation = { kind: "rejected", requestId, result };
    });

    return result;
  }
}
