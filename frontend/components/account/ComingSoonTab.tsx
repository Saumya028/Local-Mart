export function ComingSoonTab({ title, description }: { title: string; description: string }) {
  return (
    <div className="bg-white rounded-2xl border border-gray-100 p-8 text-center">
      <p className="font-semibold text-gray-900">{title}</p>
      <p className="text-sm text-gray-500 mt-1 max-w-sm mx-auto">{description}</p>
    </div>
  );
}
