export type AppNotification = {
  id: string;
  kind: string;
  title: string;
  body: string;
  link: string | null;
  created_at: string;
  read_at: string | null;
};

export type NotificationList = {
  items: AppNotification[];
  unread_count: number;
  next_before: string | null;
};
