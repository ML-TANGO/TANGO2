# Clean All
# kubectl delete all --all && kubectl delete pvc,pv --all

# Patch All PVs
kubectl get pv | tail -n+2 | awk '$5 == "Released" {print $1}' | xargs -I{} kubectl patch pv {} --type='merge' -p '{"spec":{"claimRef": null}}'

# Create Storage Class, PVC, Pod
kubectl apply -f sc.yaml
kubectl apply -f pvc.yaml
kubectl apply -f pod.yaml

while true;
do
    pod_status=$(kubectl get pod -l env=azure --no-headers=true --output=jsonpath='{.items[*].status.phase}')

    if [ "$pod_status" == "Running" ]; then
        echo "Init PV pod is now running and ready."
        break
    elif [ "$pod_status" == "Pending" ]; then
        continue
    elif [ -z "$pod_status" ]; then
        continue
    else
        echo "Pod is in an unexpected state: $pod_status"
        exit 1
    fi
    sleep 1
done

# Copy Files
echo "Copying files..."
kubectl cp /root/.kube init-pv-pod:/data/
kubectl cp /jfbcore_msa/bin/built_in_models init-pv-pod:/data/
echo "Done"

# Release PV by deleting PVC
kubectl delete -f pod.yaml && kubectl delete -f pvc.yaml

# Change all PV status from Released to Available
kubectl get pv | tail -n+2 | awk '$5 == "Released" {print $1}' | xargs -I{} kubectl patch pv {} --type='merge' -p '{"spec":{"claimRef": null}}'

echo "Init PVs now in Available Status."