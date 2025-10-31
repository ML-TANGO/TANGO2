# Patch All Released PV into Available Status
kubectl get pv | tail -n+2 | awk '$5 == "Released" {print $1}' | xargs -I{} kubectl patch pv {} --type='merge' -p '{"spec":{"claimRef": null}}'