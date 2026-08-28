# ตั้ง NFS server บนเครื่อง 192.168.10.63 (สำหรับ case-service uploads)

`case-service` รันอยู่ 2-5 replicas (HPA) กระจายไปหลาย node ในคลัสเตอร์ จะใช้
`hostPath` ตรงๆ ไม่ได้ (replica ที่ไม่ได้ลงบน node 63 จะมองไม่เห็นไฟล์ที่ replica
อื่นเซฟไว้) เลยต้องแชร์โฟลเดอร์ผ่าน NFS แทน แล้วให้ทุก node mount ได้เหมือนกัน

## 1. บนเครื่อง 192.168.10.63 (NFS server)

```bash
# Debian/Ubuntu
sudo apt update && sudo apt install -y nfs-kernel-server

sudo mkdir -p /srv/nfs/vcare/case-service/uploads/welfare-evidence
sudo mkdir -p /srv/nfs/vcare/case-service/uploads/file-payments

# case-service container รันเป็น root (ไม่มี USER ใน Dockerfile) แต่ NFS จะ
# root_squash root -> nobody โดย default ต้องเปิด no_root_squash ให้ container
# เขียนไฟล์ได้ ไม่งั้นจะเจอ Permission denied ตอนอัปโหลด
sudo chown -R nobody:nogroup /srv/nfs/vcare
sudo chmod -R 0770 /srv/nfs/vcare

# แก้ /etc/exports — จำกัดเฉพาะ subnet ของคลัสเตอร์ (ปรับ CIDR ตามจริง)
echo "/srv/nfs/vcare/case-service/uploads 192.168.10.0/24(rw,sync,no_subtree_check,no_root_squash)" \
  | sudo tee -a /etc/exports

sudo exportfs -ra
sudo systemctl enable --now nfs-kernel-server
```

ตรวจสอบจากเครื่องอื่นในวง (เช่น master 192.168.10.33):

```bash
showmount -e 192.168.10.63
```

## 2. บนทุก node ของ k8s cluster (master + worker ทุกตัวที่ pod อาจถูก schedule ไปลง)

```bash
# Debian/Ubuntu
sudo apt update && sudo apt install -y nfs-common

# RHEL/CentOS
sudo dnf install -y nfs-utils
```

ถ้าไม่ลง client package นี้ pod จะ `ContainerCreating` ค้าง พร้อม event
`MountVolume.SetUp failed ... mount: wrong fs type`

## 3. Apply manifest

```bash
kubectl apply -f k8s/case-service-storage.yml
kubectl apply -f k8s/deployment.yml
kubectl -n vcare get pvc vcare-case-service-uploads-pvc
kubectl -n vcare describe pod -l app=vcare-case-service   # เช็ค volume mount ผ่านไหม
```

## Beta

Beta ใช้ export path แยกจาก main คนละชุด กัน uploads ปนกัน: บนเครื่อง 63 ให้
สร้างเพิ่ม `/srv/nfs/vcare-beta/case-service/uploads/{welfare-evidence,file-payments}`
และเพิ่มบรรทัด `/etc/exports` แยกสำหรับ path นี้ (`chown`/`chmod` เหมือนของ main)
แล้ว apply `k8s/case-service-storage-beta.yml` แทน `case-service-storage.yml`

ก่อน apply PVC ใหม่ ถ้า `vcare-case-service-beta` เคยแชร์ PVC กับ main มาก่อน
(มีไฟล์ upload เก่าอยู่แล้ว และ evidence record ใน DB อ้างถึงไฟล์พวกนั้น) ต้อง
ก็อปไฟล์เดิมมาที่ path ใหม่ก่อน ไม่งั้น record เก่าจะอ่านไฟล์ไม่เจอ:

```bash
# รันบนเครื่อง 63 เอง (path ต้นทาง-ปลายทางอยู่เครื่องเดียวกัน)
sudo cp -a /srv/nfs/vcare/case-service/uploads/. /srv/nfs/vcare-beta/case-service/uploads/
sudo chown -R nobody:nogroup /srv/nfs/vcare-beta
sudo chmod -R 0770 /srv/nfs/vcare-beta
```

## หมายเหตุ

- เดิม docker-compose mount แยก 2 host path เข้า 2 container path — ในแบบ k8s
  ใช้ PVC เดียวแต่ mount 2 จุดด้วย `subPath` (`welfare-evidence`,
  `file-payments`) ซึ่งเทียบเท่ากัน ไม่ต้องสร้าง PV/PVC แยกสองชุด
- ระยะยาวแนะนำย้ายไปใช้ MinIO (S3 API) ที่มีอยู่แล้วบนเครื่อง 63 แทน filesystem
  เพราะไม่ต้องพึ่ง NFS/hostPath เลย แต่ต้องแก้โค้ด case-service ให้
  upload/read ผ่าน S3 client แทน local path — งานนี้แค่ทำ NFS ให้ก่อนตามที่ขอ
